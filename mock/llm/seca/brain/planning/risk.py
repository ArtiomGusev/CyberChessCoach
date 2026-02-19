def risk_adjusted_reward(
    r_delta,
    c_delta,
    r_unc,
    c_unc,
    risk_lambda: float = 0.5,
):
    mean_reward = r_delta + 0.3 * c_delta
    uncertainty = r_unc + 0.3 * c_unc

    return mean_reward - risk_lambda * uncertainty
