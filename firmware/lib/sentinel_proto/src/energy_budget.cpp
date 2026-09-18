#include "sentinel_proto/energy_budget.h"

namespace sentinel {

EnergyBudget::EnergyBudget(float capacity_j, float refill_rate_j_per_s, float initial_j)
    : capacity_j_(capacity_j),
      refill_rate_j_per_s_(refill_rate_j_per_s),
      balance_j_(initial_j >= 0.0f ? initial_j : capacity_j) {
    if (balance_j_ > capacity_j_) balance_j_ = capacity_j_;
}

void EnergyBudget::tick(uint32_t now_ms) {
    if (!initialized_) {
        // First call just establishes the clock -- there's no elapsed
        // interval to refill over yet.
        last_tick_ms_ = now_ms;
        initialized_ = true;
        return;
    }
    if (now_ms <= last_tick_ms_) return; // clock didn't advance (or wrapped -- ignore this tick)

    uint32_t elapsed_ms = now_ms - last_tick_ms_;
    last_tick_ms_ = now_ms;

    float refill = refill_rate_j_per_s_ * (static_cast<float>(elapsed_ms) / 1000.0f);
    balance_j_ += refill;
    if (balance_j_ > capacity_j_) balance_j_ = capacity_j_;
}

bool EnergyBudget::can_afford(float cost_j, uint32_t now_ms) {
    tick(now_ms);
    return balance_j_ >= cost_j;
}

bool EnergyBudget::spend(float cost_j, uint32_t now_ms) {
    tick(now_ms);
    if (balance_j_ < cost_j) return false;
    balance_j_ -= cost_j;
    return true;
}

void EnergyBudget::credit(float amount_j) {
    balance_j_ += amount_j;
    if (balance_j_ > capacity_j_) balance_j_ = capacity_j_;
    if (balance_j_ < 0.0f) balance_j_ = 0.0f;
}

} // namespace sentinel
