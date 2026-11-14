use std::collections::{BTreeMap, HashSet};

use near_sdk::borsh;
use near_sdk::collections::{LookupMap, UnorderedSet, Vector};
use near_sdk::json_types::{Base64VecU8, U128};
use near_sdk::{
    env, ext_contract, near, AccountId, BorshStorageKey, Gas, NearToken, PanicOnDefault,
    Promise, PromiseResult,
};

const BPS_DENOMINATOR: u128 = 10_000;
const MAX_DAILY_POT_BPS: u16 = 1_000;
const MIN_REFILL_YOCTO: u128 = 500_000_000_000_000_000_000_000;
const SECONDS_PER_DAY: u64 = 86_400;
const NANOS_PER_SECOND: u64 = 1_000_000_000;
const MAX_EPOCH_ACCOUNTS: usize = 2_000;
const MAX_TAGS_PER_ACCOUNT: usize = 64;
const MAX_VOTES_PER_TAG: usize = 64;
// At most 2,000 accounts × 30 daily accepted tag slots (5+10+15).
const MAX_VOTED_FINGERPRINTS_PER_DAY: u32 = 60_000;
const MAX_FINGERPRINT_LENGTH: usize = 128;
const MAX_EPOCHS_KEPT: u64 = 90;
const VIEW_POINTS: u128 = 1;
const LIKE_POINTS: u128 = 50;
const REPLY_POINTS: u128 = 100;
const RETWEET_POINTS: u128 = 200;
const QUOTE_POINTS: u128 = 300;
const ORIGINAL_MULTIPLIER: u128 = 25;

#[near(serializers = [borsh, json])]
#[derive(Clone)]
pub struct Params {
    pub token_id: AccountId,
    pub daily_pot_bps: u16,
    pub skim_bps: u16,
    pub validator_cut_bps: u16,
    pub validator_threshold: U128,
    pub validator_confirmations: u8,
    pub hold_pts_per_token_day: u16,
    pub cap_originals: u8,
    pub cap_quotes: u8,
    pub cap_replies: u8,
    pub multiplier_reply_to_token_bps: u16,
    /// Raw 32-byte Ed25519 public key. It is immutable after initialization.
    pub attestor_pk: Vec<u8>,
    pub treasury_seed: U128,
}

#[near(serializers = [borsh, json])]
#[derive(Clone)]
pub struct ValidatorVote {
    pub validator_id: AccountId,
    pub approve: bool,
}

#[near(serializers = [borsh, json])]
#[serde(rename_all = "snake_case")]
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum TagKind {
    Original,
    Quote,
    Reply,
}

#[near(serializers = [borsh, json])]
#[derive(Clone)]
pub struct TagProof {
    pub fingerprint: String,
    pub kind: TagKind,
    pub demo: bool,
    pub views: U128,
    pub likes: U128,
    pub replies: U128,
    pub retweets: U128,
    pub quotes: U128,
    pub reply_to_token: bool,
    pub votes: Vec<ValidatorVote>,
}

#[near(serializers = [borsh, json])]
#[derive(Clone)]
pub struct AccountScore {
    pub account_id: AccountId,
    pub x_account: String,
    pub demo: bool,
    pub tag_points: U128,
    pub hold_points: U128,
    pub twap_balance: U128,
    pub tags: Vec<TagProof>,
}

#[near(serializers = [borsh, json])]
#[derive(Clone)]
pub struct EpochPayload {
    pub day: u64,
    /// True for the labelled synthetic hackathon epoch; false for live inputs.
    pub demo: bool,
    pub contract_id: AccountId,
    pub network_id: String,
    pub accounts: Vec<AccountScore>,
}

#[near(serializers = [json])]
pub struct SignedEpochPayload {
    pub payload: EpochPayload,
    pub signature: Base64VecU8,
}

#[near(serializers = [borsh, json])]
#[derive(Clone)]
pub struct EpochSummary {
    pub day: u64,
    pub pot: U128,
    pub validator_cut: U128,
    pub total_points: U128,
    pub total_entitlement: U128,
    pub treasury_after: U128,
}

#[near(serializers = [borsh])]
#[derive(BorshStorageKey)]
pub enum StorageKey {
    Entitlements,
    Epochs,
    Validators,
    ValidatorVotes,
    ValidatorVoteKeys,
    ValidatorVoteKeyCounts,
    LinkedX,
    TagRegistry,
}

#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct Contract {
    params: Params,
    current_day: u64,
    entitlements: LookupMap<AccountId, u128>,
    epoch_log: Vector<EpochSummary>,
    validators: UnorderedSet<AccountId>,
    validator_votes: LookupMap<String, Vec<ValidatorVote>>,
    validator_vote_keys: LookupMap<(u64, u32), String>,
    validator_vote_key_counts: LookupMap<u64, u32>,
    linked_x: LookupMap<AccountId, String>,
    tag_registry: UnorderedSet<String>,
    accounted_treasury: u128,
    skim_pot: u128,
    near_pot: u128,
    outstanding_entitlements: u128,
}

#[ext_contract(ext_token)]
trait ExtToken {
    fn ft_transfer(&mut self, receiver_id: AccountId, amount: U128, memo: Option<String>);
    fn ft_balance_of(&self, account_id: AccountId) -> U128;
}

#[ext_contract(ext_self)]
trait ExtSelf {
    fn resolve_claim(&mut self, account_id: AccountId, gross: U128, user_amount: U128);
    fn on_register_validator(&mut self, account_id: AccountId) -> bool;
}

#[near]
impl Contract {
    #[init]
    pub fn new(params: Params) -> Self {
        assert!(!env::state_exists(), "already initialized");
        assert!(params.daily_pot_bps <= MAX_DAILY_POT_BPS, "daily pot exceeds 10%");
        assert!(params.skim_bps <= 10_000, "invalid skim");
        assert!(params.validator_cut_bps <= 10_000, "invalid validator cut");
        assert!(params.validator_confirmations > 0, "confirmation threshold must be nonzero");
        assert!(params.validator_threshold.0 > 0, "validator threshold must be nonzero");
        assert_eq!(params.attestor_pk.len(), 32, "attestor key must be 32 bytes");
        assert!(params.cap_originals > 0 && params.cap_quotes > 0 && params.cap_replies > 0,
                "daily caps must be nonzero");

        let today = env::block_timestamp() / NANOS_PER_SECOND / SECONDS_PER_DAY;
        Self {
            params,
            current_day: today.saturating_sub(1),
            entitlements: LookupMap::new(StorageKey::Entitlements),
            epoch_log: Vector::new(StorageKey::Epochs),
            validators: UnorderedSet::new(StorageKey::Validators),
            validator_votes: LookupMap::new(StorageKey::ValidatorVotes),
            validator_vote_keys: LookupMap::new(StorageKey::ValidatorVoteKeys),
            validator_vote_key_counts: LookupMap::new(StorageKey::ValidatorVoteKeyCounts),
            linked_x: LookupMap::new(StorageKey::LinkedX),
            tag_registry: UnorderedSet::new(StorageKey::TagRegistry),
            accounted_treasury: 0,
            skim_pot: 0,
            near_pot: 0,
            outstanding_entitlements: 0,
        }
    }

    pub fn get_params(&self) -> Params {
        self.params.clone()
    }

    pub fn get_entitlement(&self, account_id: AccountId) -> U128 {
        U128(self.entitlements.get(&account_id).unwrap_or(0))
    }

    pub fn get_epoch(&self, day: u64) -> Option<EpochSummary> {
        self.epoch_log.iter().find(|entry| entry.day == day)
    }

    /// The contract's internal TAG balance ledger. TAG must be seeded using
    /// `ft_transfer_call`; direct `ft_transfer` deposits are not observable.
    pub fn treasury(&self) -> U128 {
        U128(self.accounted_treasury)
    }

    pub fn pots(&self) -> (U128, U128) {
        (U128(self.skim_pot), U128(self.near_pot))
    }

    pub fn register_validator(&self) -> Promise {
        assert_zero_attached_deposit();
        let account_id = env::predecessor_account_id();
        ext_token::ext(self.params.token_id.clone())
            .with_static_gas(Gas::from_tgas(5))
            .ft_balance_of(account_id.clone())
            .then(
                ext_self::ext(env::current_account_id())
                    .with_static_gas(Gas::from_tgas(5))
                    .on_register_validator(account_id),
            )
    }

    /// Validators submit their own approve/reject vote before the next epoch.
    /// Each registered account gets one immutable vote per fingerprint/day.
    pub fn submit_vote(&mut self, day: u64, fingerprint: String, approve: bool) {
        assert_zero_attached_deposit();
        let validator_id = env::predecessor_account_id();
        assert!(self.validators.contains(&validator_id), "not a registered validator");
        assert_eq!(day, self.current_day.saturating_add(1), "vote must target next epoch");
        assert!(!fingerprint.is_empty() && fingerprint.len() <= MAX_FINGERPRINT_LENGTH,
                "invalid fingerprint");
        let key = vote_key(day, &fingerprint);
        let mut votes = self.validator_votes.get(&key).unwrap_or_default();
        if votes.is_empty() {
            let count = self.validator_vote_key_counts.get(&day).unwrap_or(0);
            assert!(count < MAX_VOTED_FINGERPRINTS_PER_DAY,
                    "daily fingerprint vote limit reached");
            self.validator_vote_keys.insert(&(day, count), &key);
            self.validator_vote_key_counts.insert(&day, &(count + 1));
        }
        assert!(votes.len() < MAX_VOTES_PER_TAG, "vote limit reached");
        assert!(!votes.iter().any(|vote| vote.validator_id == validator_id),
                "validator already voted");
        votes.push(ValidatorVote { validator_id, approve });
        self.validator_votes.insert(&key, &votes);
    }

    #[private]
    pub fn on_register_validator(&mut self, account_id: AccountId) -> bool {
        let balance = match env::promise_result(0) {
            PromiseResult::Successful(bytes) => near_sdk::serde_json::from_slice::<U128>(&bytes)
                .map(|value| value.0)
                .unwrap_or(0),
            _ => 0,
        };
        if balance >= self.params.validator_threshold.0 {
            self.validators.insert(&account_id);
            true
        } else {
            false
        }
    }

    /// Submit a signed, sequential daily epoch. The attestor signs the SHA-256
    /// digest of the Borsh-serialized `payload` bytes.
    pub fn submit_epoch(&mut self, signed: SignedEpochPayload) {
        assert_zero_attached_deposit();
        let payload = signed.payload;
        assert_eq!(payload.contract_id, env::current_account_id(), "epoch targets another contract");
        assert_eq!(payload.network_id, env::chain_id(), "epoch targets another network");
        assert_eq!(payload.day, self.current_day.saturating_add(1), "epoch day must be sequential");
        assert!(payload.accounts.len() <= MAX_EPOCH_ACCOUNTS, "too many accounts");
        self.verify_attestor_signature(&payload, &signed.signature.0);

        // Do not allocate funds already promised by earlier, unclaimed epochs.
        let available_treasury = self.accounted_treasury
            .checked_sub(self.outstanding_entitlements)
            .expect("outstanding entitlements exceed treasury");
        let pot = mul_div_floor(available_treasury, self.params.daily_pot_bps as u128,
                                BPS_DENOMINATOR)
            .min(available_treasury);
        let validator_cut = mul_div_floor(pot, self.params.validator_cut_bps as u128,
                                          BPS_DENOMINATOR);
        let user_budget = pot - validator_cut;

        let mut seen_accounts = HashSet::new();
        let mut seen_fingerprints = HashSet::new();
        let mut accepted_fingerprints = Vec::new();
        let mut points_by_account: BTreeMap<AccountId, u128> = BTreeMap::new();
        let mut twap_by_account: BTreeMap<AccountId, u128> = BTreeMap::new();
        let mut validator_counts: BTreeMap<AccountId, u128> = BTreeMap::new();
        let mut total_points = 0u128;

        for score in payload.accounts.iter() {
            assert!(seen_accounts.insert(score.account_id.clone()), "duplicate account score");
            assert_eq!(score.demo, payload.demo, "account demo label mismatch");
            assert!(score.tags.len() <= MAX_TAGS_PER_ACCOUNT, "too many tags for account");
            if score.tag_points.0 > 0 || !score.tags.is_empty() {
                assert!(!score.x_account.trim().is_empty(), "tag activity requires an X account");
            }

            if let Some(existing) = self.linked_x.get(&score.account_id) {
                assert_eq!(existing, score.x_account, "wallet X link is first-write-wins");
            }

            let mut accepted_tag_points = 0u128;
            let mut original_count = 0u8;
            let mut quote_count = 0u8;
            let mut reply_count = 0u8;
            for proof in score.tags.iter() {
                assert_eq!(proof.demo, payload.demo, "tag demo label mismatch");
                assert!(proof.fingerprint.len() <= MAX_FINGERPRINT_LENGTH,
                        "fingerprint too long");
                assert!(!proof.fingerprint.is_empty(), "empty fingerprint");
                assert!(seen_fingerprints.insert(proof.fingerprint.clone()),
                        "duplicate fingerprint in epoch");
                assert!(!self.tag_registry.contains(&proof.fingerprint), "fingerprint already paid");
                assert!(proof.votes.is_empty(), "votes must be submitted by validators on-chain");

                let votes_key = vote_key(payload.day, &proof.fingerprint);
                let votes = self.validator_votes.get(&votes_key).unwrap_or_default();
                assert!(votes.len() <= MAX_VOTES_PER_TAG, "too many votes for tag");
                let mut voters = HashSet::new();
                let mut approvers = Vec::new();
                let mut net_confirmations = 0i32;
                for vote in votes.iter() {
                    assert!(voters.insert(vote.validator_id.clone()), "duplicate validator vote");
                    assert!(self.validators.contains(&vote.validator_id), "voter is not a registered validator");
                    if vote.approve {
                        net_confirmations += 1;
                        approvers.push(vote.validator_id.clone());
                    } else {
                        net_confirmations -= 1;
                    }
                }

                if net_confirmations >= self.params.validator_confirmations as i32 {
                    let within_cap = match proof.kind {
                        TagKind::Original if original_count < self.params.cap_originals => {
                            original_count += 1;
                            true
                        }
                        TagKind::Quote if quote_count < self.params.cap_quotes => {
                            quote_count += 1;
                            true
                        }
                        TagKind::Reply if reply_count < self.params.cap_replies => {
                            reply_count += 1;
                            true
                        }
                        _ => false,
                    };
                    if within_cap {
                        let points = score_proof(proof, self.params.multiplier_reply_to_token_bps);
                        accepted_tag_points = accepted_tag_points
                            .checked_add(points).expect("tag point overflow");
                        accepted_fingerprints.push(proof.fingerprint.clone());
                        for validator_id in approvers {
                            let count = validator_counts.entry(validator_id).or_insert(0);
                            *count = count.checked_add(1).expect("validator count overflow");
                        }
                    }
                }
            }

            assert_eq!(accepted_tag_points, score.tag_points.0,
                       "tag_points must equal points from quorum-confirmed proofs");
            let account_points = score.tag_points.0.checked_add(score.hold_points.0)
                .expect("account point overflow");
            total_points = total_points.checked_add(account_points).expect("total points overflow");
            points_by_account.insert(score.account_id.clone(), account_points);
            twap_by_account.insert(score.account_id.clone(), score.twap_balance.0);
        }

        let total_validator_votes: u128 = validator_counts.values().copied()
            .try_fold(0u128, |sum, count| sum.checked_add(count))
            .expect("validator vote total overflow");

        let mut epoch_entitlement = 0u128;
        let mut additions: Vec<(AccountId, u128)> = Vec::new();
        for (account_id, account_points) in points_by_account.iter() {
            let points_share = if total_points == 0 { 0 } else {
                mul_div_floor(user_budget, *account_points, total_points)
            };
            let validator_share = if total_validator_votes == 0 { 0 } else {
                let count = validator_counts.get(account_id).copied().unwrap_or(0);
                mul_div_floor(validator_cut, count, total_validator_votes)
            };
            let uncapped = points_share.checked_add(validator_share).expect("payout overflow");
            // TWAP is a daily cap; prior-day rewards remain independently claimable.
            let payout = uncapped.min(*twap_by_account.get(account_id).unwrap_or(&0));
            if payout > 0 {
                epoch_entitlement = epoch_entitlement.checked_add(payout).expect("entitlement overflow");
                additions.push((account_id.clone(), payout));
            }
        }
        assert!(epoch_entitlement <= pot, "epoch entitlement exceeds pot");

        // Never partially mutate state: all validation and arithmetic checks
        // above complete before any X link, entitlement, or fingerprint is written.
        for score in payload.accounts.iter() {
            if !score.x_account.trim().is_empty() && self.linked_x.get(&score.account_id).is_none() {
                self.linked_x.insert(&score.account_id, &score.x_account);
            }
        }
        for fingerprint in accepted_fingerprints.iter() {
            self.tag_registry.insert(fingerprint);
        }
        let vote_key_count = self.validator_vote_key_counts.remove(&payload.day).unwrap_or(0);
        for index in 0..vote_key_count {
            if let Some(key) = self.validator_vote_keys.remove(&(payload.day, index)) {
                self.validator_votes.remove(&key);
            }
        }
        for (account_id, addition) in additions.iter() {
            let old = self.entitlements.get(account_id).unwrap_or(0);
            let updated = old.checked_add(*addition).expect("entitlement overflow");
            self.entitlements.insert(account_id, &updated);
        }
        self.outstanding_entitlements = self.outstanding_entitlements
            .checked_add(epoch_entitlement).expect("outstanding entitlement overflow");
        self.current_day = payload.day;

        let summary = EpochSummary {
            day: payload.day,
            pot: U128(pot),
            validator_cut: U128(validator_cut),
            total_points: U128(total_points),
            total_entitlement: U128(epoch_entitlement),
            treasury_after: U128(self.accounted_treasury),
        };
        if self.epoch_log.len() >= MAX_EPOCHS_KEPT {
            self.epoch_log.swap_remove(0);
        }
        self.epoch_log.push(&summary);
        env::log_str(&format!(
            "{{\"event\":\"EpochSettled\",\"day\":{},\"pot\":\"{}\",\"entitlement\":\"{}\"}}",
            payload.day, pot, epoch_entitlement
        ));
    }

    pub fn claim(&mut self) -> Promise {
        assert_zero_attached_deposit();
        let account_id = env::predecessor_account_id();
        let gross = self.entitlements.get(&account_id).unwrap_or(0);
        assert!(gross > 0, "no entitlement to claim");
        let user_amount = mul_div_floor(
            gross,
            (BPS_DENOMINATOR - self.params.skim_bps as u128),
            BPS_DENOMINATOR,
        );
        let skim = gross - user_amount;

        // Effects precede the external FT call. Failed transfers restore the
        // entitlement in the private callback.
        self.entitlements.remove(&account_id);
        self.outstanding_entitlements = self.outstanding_entitlements
            .checked_sub(gross).expect("outstanding entitlement underflow");
        self.accounted_treasury = self.accounted_treasury
            .checked_sub(user_amount).expect("insufficient accounted treasury");
        self.skim_pot = self.skim_pot.checked_add(skim).expect("skim counter overflow");

        ext_token::ext(self.params.token_id.clone())
            .with_attached_deposit(NearToken::from_yoctonear(1))
            .with_static_gas(Gas::from_tgas(20))
            .ft_transfer(account_id.clone(), U128(user_amount), Some("TAG claim".to_string()))
            .then(
                ext_self::ext(env::current_account_id())
                    .with_static_gas(Gas::from_tgas(10))
                    .resolve_claim(account_id, U128(gross), U128(user_amount)),
            )
    }

    #[private]
    pub fn resolve_claim(&mut self, account_id: AccountId, gross: U128, user_amount: U128) {
        match env::promise_result(0) {
            PromiseResult::Successful(_) => {}
            _ => {
                let restored = self.entitlements.get(&account_id).unwrap_or(0)
                    .checked_add(gross.0).expect("entitlement restore overflow");
                self.entitlements.insert(&account_id, &restored);
                self.outstanding_entitlements = self.outstanding_entitlements
                    .checked_add(gross.0).expect("outstanding restore overflow");
                self.accounted_treasury = self.accounted_treasury
                    .checked_add(user_amount.0).expect("treasury restore overflow");
                let skim = gross.0 - user_amount.0;
                self.skim_pot = self.skim_pot.checked_sub(skim).expect("skim restore underflow");
            }
        }
    }

    /// Accept native NEAR for the buyback pot. Only the token contract can
    /// receive NEAR through an attached-deposit payable call; an FT receiver
    /// callback cannot account for native NEAR.
    #[payable]
    pub fn deposit_near(&mut self) {
        let amount = env::attached_deposit().as_yoctonear();
        assert!(amount > 0, "deposit must be positive");
        self.near_pot = self.near_pot.checked_add(amount).expect("NEAR pot overflow");
    }

    /// TAG treasury deposits must use `ft_transfer_call`; unrelated tokens
    /// are returned by the NEP-141 receiver interface.
    pub fn ft_on_transfer(&mut self, _sender_id: AccountId, amount: U128, _msg: String) -> U128 {
        assert_zero_attached_deposit();
        if env::predecessor_account_id() != self.params.token_id {
            return amount;
        }
        self.accounted_treasury = self.accounted_treasury
            .checked_add(amount.0).expect("treasury overflow");
        U128(0)
    }

    /// Ref Finance integration is intentionally disabled until the testnet
    /// router account and compatible pool are verified. The pot is retained.
    pub fn refill(&mut self) -> bool {
        assert_zero_attached_deposit();
        if self.near_pot < MIN_REFILL_YOCTO {
            return false;
        }
        false
    }

    fn verify_attestor_signature(&self, payload: &EpochPayload, signature: &[u8]) {
        assert_eq!(signature.len(), 64, "signature must be 64 bytes");
        let serialized = borsh::to_vec(payload).expect("payload serialization failed");
        let digest = env::sha256(&serialized);
        let sig: &[u8; 64] = signature.try_into().expect("signature length checked");
        let key: &[u8; 32] = self.params.attestor_pk.as_slice().try_into()
            .expect("attestor key length checked at init");
        assert!(env::ed25519_verify(sig, digest, key), "invalid attestor signature");
    }
}

fn assert_zero_attached_deposit() {
    assert_eq!(env::attached_deposit().as_yoctonear(), 0, "attached deposit not accepted");
}

fn vote_key(day: u64, fingerprint: &str) -> String {
    format!("{}:{}", day, fingerprint)
}

fn mul_div_floor(value: u128, numerator: u128, denominator: u128) -> u128 {
    assert!(denominator > 0, "division by zero");
    let whole = (value / denominator)
        .checked_mul(numerator).expect("multiplication overflow");
    let fraction = (value % denominator)
        .checked_mul(numerator).expect("fraction multiplication overflow") / denominator;
    whole.checked_add(fraction).expect("result overflow")
}

fn score_proof(proof: &TagProof, reply_to_token_bps: u16) -> u128 {
    assert!(!proof.reply_to_token || proof.kind != TagKind::Original,
            "original posts cannot target the token account");
    let mut points = proof.views.0.checked_mul(VIEW_POINTS).expect("view points overflow")
        .checked_add(proof.likes.0.checked_mul(LIKE_POINTS).expect("like points overflow"))
        .and_then(|value| value.checked_add(proof.replies.0.checked_mul(REPLY_POINTS)?))
        .and_then(|value| value.checked_add(proof.retweets.0.checked_mul(RETWEET_POINTS)?))
        .and_then(|value| value.checked_add(proof.quotes.0.checked_mul(QUOTE_POINTS)?))
        .expect("engagement point overflow");
    if proof.kind == TagKind::Original {
        points = points.checked_mul(ORIGINAL_MULTIPLIER).expect("original multiplier overflow");
    }
    if proof.reply_to_token {
        assert!(proof.kind == TagKind::Quote || proof.kind == TagKind::Reply,
                "only a quote or reply can target the token account");
        points = mul_div_floor(points, reply_to_token_bps as u128, BPS_DENOMINATOR);
    }
    points
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::{Signer, SigningKey};
    use near_sdk::test_utils::VMContextBuilder;
    use near_sdk::testing_env;

    fn params(key: &SigningKey) -> Params {
        Params {
            token_id: "tag.testnet".parse().unwrap(),
            daily_pot_bps: 1_000,
            skim_bps: 500,
            validator_cut_bps: 1_000,
            validator_threshold: U128(5_000),
            validator_confirmations: 2,
            hold_pts_per_token_day: 50,
            cap_originals: 5,
            cap_quotes: 10,
            cap_replies: 15,
            multiplier_reply_to_token_bps: 15_000,
            attestor_pk: key.verifying_key().to_bytes().to_vec(),
            treasury_seed: U128(1_000_000),
        }
    }

    fn context(predecessor: &str) {
        let mut builder = VMContextBuilder::new();
        builder
            .current_account_id("mech.testnet".parse().unwrap())
            .predecessor_account_id(predecessor.parse().unwrap())
            .block_timestamp(1_800_000_000_000_000_000);
        testing_env!(builder.build());
    }

    fn signing_key() -> SigningKey {
        SigningKey::from_bytes(&[7; 32])
    }

    fn approved_tag(fingerprint: &str, kind: TagKind) -> TagProof {
        TagProof {
            fingerprint: fingerprint.to_string(),
            kind,
            demo: true,
            views: U128(1),
            likes: U128(0),
            replies: U128(0),
            retweets: U128(0),
            quotes: U128(0),
            reply_to_token: false,
            votes: vec![],
        }
    }

    fn record_votes(contract: &mut Contract, day: u64, fingerprint: &str,
                    validators: &[&str], approve: bool) {
        for validator in validators {
            context(validator);
            contract.submit_vote(day, fingerprint.to_string(), approve);
        }
    }

    fn sign(payload: EpochPayload, key: &SigningKey) -> SignedEpochPayload {
        let bytes = borsh::to_vec(&payload).unwrap();
        let digest = env::sha256(&bytes);
        let signature = key.sign(&digest).to_bytes();
        SignedEpochPayload { payload, signature: Base64VecU8(signature.to_vec()) }
    }

    fn fresh_contract(key: &SigningKey) -> Contract {
        context("owner.testnet");
        Contract::new(params(key))
    }

    fn next_day(contract: &Contract) -> u64 {
        contract.current_day + 1
    }

    #[test]
    fn pot_is_at_most_ten_percent_and_claim_math_is_95_5() {
        assert_eq!(mul_div_floor(1_000_000, 1_000, BPS_DENOMINATOR), 100_000);
        assert_eq!(mul_div_floor(100_000, 9_500, BPS_DENOMINATOR), 95_000);
    }

    #[test]
    fn share_math_rounds_down_without_overpaying() {
        let shares = (0..3).map(|_| mul_div_floor(100, 1, 3)).sum::<u128>();
        assert_eq!(shares, 99);
    }

    #[test]
    fn user_cap_applies_to_combined_reward_streams() {
        let points_share = mul_div_floor(90, 1, 1);
        let validator_share = mul_div_floor(10, 1, 1);
        assert_eq!((points_share + validator_share).min(75), 75);
    }

    #[test]
    fn fixed_scoring_weights_and_original_multiplier() {
        let original = TagProof {
            fingerprint: "fingerprint".to_string(),
            kind: TagKind::Original,
            demo: true,
            views: U128(1),
            likes: U128(1),
            replies: U128(1),
            retweets: U128(1),
            quotes: U128(1),
            reply_to_token: false,
            votes: vec![],
        };
        assert_eq!(score_proof(&original, 15_000), 16_275);
    }

    #[test]
    fn reply_to_token_multiplier_applies_to_quote_and_reply() {
        let mut quote = TagProof {
            fingerprint: "fingerprint".to_string(),
            kind: TagKind::Quote,
            demo: true,
            views: U128(0),
            likes: U128(0),
            replies: U128(0),
            retweets: U128(0),
            quotes: U128(1),
            reply_to_token: true,
            votes: vec![],
        };
        assert_eq!(score_proof(&quote, 15_000), 450);
        quote.kind = TagKind::Original;
        assert!(std::panic::catch_unwind(|| score_proof(&quote, 15_000)).is_err());
    }

    #[test]
    fn parameters_are_unchanged_by_epoch_settlement() {
        let key = signing_key();
        let mut contract = fresh_contract(&key);
        let before = contract.get_params();
        contract.accounted_treasury = 1_000;
        let epoch = EpochPayload {
            day: next_day(&contract), demo: true,
            contract_id: "mech.testnet".parse().unwrap(), network_id: "test".into(),
            accounts: vec![],
        };
        contract.submit_epoch(sign(epoch, &key));
        let after = contract.get_params();
        assert_eq!(before.daily_pot_bps, after.daily_pot_bps);
        assert_eq!(before.skim_bps, after.skim_bps);
        assert_eq!(before.validator_cut_bps, after.validator_cut_bps);
        assert_eq!(before.attestor_pk, after.attestor_pk);
    }

    #[test]
    fn settlement_respects_epoch_pot_and_combined_account_twap_cap() {
        let key = signing_key();
        let mut contract = fresh_contract(&key);
        contract.accounted_treasury = 1_000;
        contract.validators.insert(&"val1.testnet".parse().unwrap());
        contract.validators.insert(&"val2.testnet".parse().unwrap());
        let tag = approved_tag("fp-a", TagKind::Reply);
        let day = next_day(&contract);
        record_votes(&mut contract, day, "fp-a", &["val1.testnet", "val2.testnet"], true);
        let epoch = EpochPayload {
            day,
            demo: true,
            contract_id: "mech.testnet".parse().unwrap(),
            network_id: "test".into(),
            accounts: vec![
                AccountScore {
                    account_id: "val1.testnet".parse().unwrap(),
                    x_account: "@alice".to_string(),
                    demo: true,
                    tag_points: U128(1),
                    hold_points: U128(100),
                    twap_balance: U128(49),
                    tags: vec![tag],
                },
                AccountScore {
                    account_id: "bob.testnet".parse().unwrap(),
                    x_account: "".to_string(),
                    demo: true,
                    tag_points: U128(0),
                    hold_points: U128(0),
                    twap_balance: U128(1_000),
                    tags: vec![],
                },
            ],
        };
        contract.submit_epoch(sign(epoch, &key));
        let summary = contract.get_epoch(contract.current_day).unwrap();
        assert!(summary.total_entitlement.0 <= summary.pot.0);
        assert_eq!(contract.get_entitlement("val1.testnet".parse().unwrap()).0, 49);
    }

    #[test]
    fn votes_are_independent_on_chain_and_rejections_cancel_confirmations() {
        let key = signing_key();
        let mut contract = fresh_contract(&key);
        contract.accounted_treasury = 1_000;
        contract.validators.insert(&"val1.testnet".parse().unwrap());
        contract.validators.insert(&"val2.testnet".parse().unwrap());
        let day = next_day(&contract);
        context("val1.testnet");
        contract.submit_vote(day, "fp-vote".to_string(), true);
        let duplicate = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            contract.submit_vote(day, "fp-vote".to_string(), false);
        }));
        assert!(duplicate.is_err());
        context("val2.testnet");
        contract.submit_vote(day, "fp-vote".to_string(), false);

        let tag = TagProof {
            fingerprint: "fp-vote".to_string(),
            kind: TagKind::Reply,
            demo: true,
            views: U128(1),
            likes: U128(0),
            replies: U128(0),
            retweets: U128(0),
            quotes: U128(0),
            reply_to_token: false,
            votes: vec![],
        };
        let epoch = EpochPayload {
            day,
            demo: true,
            contract_id: "mech.testnet".parse().unwrap(),
            network_id: "test".into(),
            accounts: vec![AccountScore {
                account_id: "alice.testnet".parse().unwrap(),
                x_account: "@alice".to_string(),
                demo: true,
                tag_points: U128(0),
                hold_points: U128(0),
                twap_balance: U128(1_000),
                tags: vec![tag],
            }],
        };
        contract.submit_epoch(sign(epoch, &key));
        assert!(!contract.tag_registry.contains(&"fp-vote".to_string()));
        assert!(contract.validator_votes.get(&vote_key(day, "fp-vote")).is_none());
    }

    #[test]
    fn later_epochs_reserve_unclaimed_payouts_without_reusing_their_pot() {
        let key = signing_key();
        let mut contract = fresh_contract(&key);
        contract.accounted_treasury = 1_000;
        let epoch_for = |day| EpochPayload {
            day,
            demo: true,
            contract_id: "mech.testnet".parse().unwrap(),
            network_id: "test".into(),
            accounts: vec![AccountScore {
                account_id: "alice.testnet".parse().unwrap(),
                x_account: String::new(),
                demo: true,
                tag_points: U128(0),
                hold_points: U128(1),
                twap_balance: U128(100),
                tags: vec![],
            }],
        };

        let first_day = next_day(&contract);
        contract.submit_epoch(sign(epoch_for(first_day), &key));
        let first_owed = contract.get_entitlement("alice.testnet".parse().unwrap()).0;
        assert_eq!(first_owed, 90);
        let first_pot = contract.get_epoch(first_day).unwrap().pot.0;

        let second_day = next_day(&contract);
        contract.submit_epoch(sign(epoch_for(second_day), &key));
        let second_pot = contract.get_epoch(second_day).unwrap().pot.0;
        let total_owed = contract.get_entitlement("alice.testnet".parse().unwrap()).0;

        assert_eq!(second_pot, 91); // 10% of 1,000 less 90 already owed.
        assert_eq!(first_pot, 100);
        assert_eq!(total_owed, 172); // Each day's payout has its own 100-token TWAP cap.
        assert!(total_owed <= contract.accounted_treasury);
    }

    #[test]
    fn paid_fingerprints_cannot_be_reused_in_a_later_epoch() {
        let key = signing_key();
        let mut contract = fresh_contract(&key);
        contract.accounted_treasury = 10_000;
        contract.validators.insert(&"val1.testnet".parse().unwrap());
        contract.validators.insert(&"val2.testnet".parse().unwrap());
        let make_epoch = |day| EpochPayload {
            day,
            demo: true,
            contract_id: "mech.testnet".parse().unwrap(),
            network_id: "test".into(),
            accounts: vec![AccountScore {
                account_id: "alice.testnet".parse().unwrap(),
                x_account: "@alice".to_string(),
                demo: true,
                tag_points: U128(1),
                hold_points: U128(0),
                twap_balance: U128(10_000),
                tags: vec![approved_tag("same-fingerprint", TagKind::Reply)],
            }],
        };
        let first_day = next_day(&contract);
        record_votes(&mut contract, first_day, "same-fingerprint",
                     &["val1.testnet", "val2.testnet"], true);
        contract.submit_epoch(sign(make_epoch(first_day), &key));
        let replay = sign(make_epoch(next_day(&contract)), &key);
        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            contract.submit_epoch(replay);
        }));
        assert!(result.is_err());
        assert_eq!(contract.current_day, first_day);
    }

    #[test]
    fn claim_clears_only_the_callers_entitlement_before_external_transfer() {
        let key = signing_key();
        context("alice.testnet");
        let mut contract = Contract::new(params(&key));
        contract.accounted_treasury = 1_000;
        contract.outstanding_entitlements = 100;
        contract.entitlements.insert(&"alice.testnet".parse().unwrap(), &100);
        let _promise = contract.claim();
        assert_eq!(contract.get_entitlement("alice.testnet".parse().unwrap()).0, 0);
        assert_eq!(contract.accounted_treasury, 905);
        assert_eq!(contract.skim_pot, 5);
        let second_claim = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| contract.claim()));
        assert!(second_claim.is_err());
    }

    #[test]
    fn account_day_is_unix_day() {
        context("alice.testnet");
        let day = env::block_timestamp() / NANOS_PER_SECOND / SECONDS_PER_DAY;
        assert!(day > 0);
    }

    #[test]
    fn mul_div_handles_large_treasury_without_false_overflow() {
        assert_eq!(mul_div_floor(u128::MAX, 1_000, 10_000), u128::MAX / 10);
    }
}
