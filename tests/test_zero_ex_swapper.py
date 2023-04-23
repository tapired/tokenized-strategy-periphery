import pytest
import ape
from ape import Contract
from utils import zero_ex_swap


######################################## UTILITY FUNCTIONS TESTS ########################################


def test_mapping_accounts_correctly(zero_ex_swapper, crv, cvx, tokens):
    # Initial rewards and targets are set correctly
    assert zero_ex_swapper.rewardTokenToTargetToken(crv) == tokens["dai"]
    assert zero_ex_swapper.rewardTokenToTargetToken(cvx) == tokens["usdc"]


def test_set_new_reward_token(zero_ex_swapper, crv, cvx, tokens, daddy):
    # new reward token weth with target dai
    zero_ex_swapper.setRewardToken(tokens["weth"], tokens["dai"], sender=daddy)

    # got his place on the mapping
    assert zero_ex_swapper.rewardTokenToTargetToken(tokens["weth"]) == tokens["dai"]

    # remaining stands still
    test_mapping_accounts_correctly(zero_ex_swapper, crv, cvx, tokens)


def test_delete_reward_token(zero_ex_swapper, crv, cvx, tokens, daddy):
    # delete one of the reward token
    zero_ex_swapper.deleteRewardToken(crv, sender=daddy)

    assert zero_ex_swapper.rewardTokenToTargetToken(cvx) == tokens["usdc"]


######################################## SWAP LOGIC TESTS ########################################

# swap() input is wrong
def test_non_reward_token_input_swap_fails(
    zero_ex_swapper, asset, tokens, whale, daddy
):
    # airdrop usdc to mock strategy
    usdc_amount = 1000 * 10**6
    asset.transfer(zero_ex_swapper.address, usdc_amount, sender=whale)

    # get a quote for selling usdc to dai
    swap_data = zero_ex_swap.getDefaultQuote("DAI", "USDC", usdc_amount)

    with ape.reverts("Zero Address"):
        zero_ex_swapper.swap(swap_data, tokens["usdc"], sender=daddy)


# swap() input is correct, but data constructed is wrong
def test_non_reward_token_data_swap_fails(zero_ex_swapper, crv, whale, daddy):
    # airdrop crv to mock strategy
    crv_amount = 1000 * 10**18
    crv.transfer(zero_ex_swapper.address, crv_amount, sender=whale)

    # get a quote for selling usdc to dai
    swap_data = zero_ex_swap.getDefaultQuote("DAI", "USDC", crv_amount)

    # fail because the swap data generated for usdc not crv
    with ape.reverts():
        zero_ex_swapper.swap(swap_data, crv, sender=daddy)


# swap() input is correct, target token is wrong
def test_true_reward_wrong_target_token(zero_ex_swapper, crv, whale, daddy):
    # airdrop crv to mock strategy
    crv_amount = 1000 * 10**18
    crv.transfer(zero_ex_swapper.address, crv_amount, sender=whale)

    # get a quote for selling crv to usdc
    swap_data = zero_ex_swap.getDefaultQuote("USDC", "CRV", 500 * 10**18)

    # We expect the target token for reward to be 0 after the swap
    # since the target token is wrongly generated in swap data we will get partial swap
    with ape.reverts("Invalid Target Token"):
        zero_ex_swapper.swap(swap_data, crv, sender=daddy)


# swap() input is correct, target token is correct but the swapped token is not reward token
# there can be 2 things happening: If the non-reward token has approval to router, we will get PartialSwap() error
# which should never happen in our case since we handle approvals correctly in strategy set methods.
# If there are no approvals given from strategy to 0x router for the token (this will be happening ideally)
# low level call will fail hence, SWAP_FAILED will thrown.
def test_non_reward_token_correct_target_token_malicious(
    zero_ex_swapper, crv, asset, whale, daddy
):
    # airdrop crv to mock strategy
    usdc_amount = 1000 * 10**6
    asset.transfer(zero_ex_swapper.address, usdc_amount, sender=whale)
    crv.transfer(
        zero_ex_swapper.address, usdc_amount * 10**12, sender=whale
    )  # it also has some crv

    # get a quote for selling usdc to dai, strategy has USDC but it's not reward token
    swap_data = zero_ex_swap.getDefaultQuote("DAI", "USDC", usdc_amount)

    with ape.reverts("SWAP_FAILED"):
        zero_ex_swapper.swap(swap_data, crv, sender=daddy)


def test_basic_swap(zero_ex_swapper, crv, cvx, tokens, whale, cvx_whale, daddy):
    # airdrop curve to mock strategy
    crv_amount = 1000 * 10**18
    crv.transfer(zero_ex_swapper.address, crv_amount, sender=whale)

    # check airdrop success
    assert crv.balanceOf(zero_ex_swapper.address) == crv_amount

    # generate swap data, we sell crv for dai
    swap_data = zero_ex_swap.getDefaultQuote("DAI", "CRV", crv_amount)

    zero_ex_swapper.swap(swap_data, crv, sender=daddy)

    # This should already be satisfied in strategy but double check
    # All crv is consumed in swap no leftovers
    assert crv.balanceOf(zero_ex_swapper.address) == 0

    # Strategy received some DAI
    dai_contract = Contract(tokens["dai"])
    assert dai_contract.balanceOf(zero_ex_swapper.address) != 0

    cvx_amount = 500 * 10**18
    cvx.transfer(zero_ex_swapper.address, cvx_amount, sender=cvx_whale)

    # check airdrop success
    assert cvx.balanceOf(zero_ex_swapper.address) == cvx_amount

    # generate swap data, we sell cvx for usdc
    swap_data = zero_ex_swap.getDefaultQuote("USDC", cvx.address, cvx_amount)

    zero_ex_swapper.swap(swap_data, cvx, sender=daddy)

    # This should already be satisfied in strategy but double check
    # All crv is consumed in swap no leftovers
    assert cvx.balanceOf(zero_ex_swapper.address) == 0

    # Strategy received some DAI
    usdc_contract = Contract(tokens["usdc"])
    assert usdc_contract.balanceOf(zero_ex_swapper.address) != 0
