#pragma once
#include <cstdint>

// Energy token bucket for EnergyGate admission control (brief v4 /
// docs/v4_energy_split.md, firmware task 3: "Energy token bucket ... on
// the gateway: joules, refills over time.").
//
// A classic token bucket, denominated in joules instead of requests: the
// gateway spends estimated-mJ-cost before letting an operation (a
// handshake at some ML-KEM level, typically) proceed, and the bucket
// refills at a fixed rate over time. When the balance can't cover a
// spend, EnergyGate's caller should challenge or drop instead of spend
// (see field_model.h's FieldClass pattern for the analogous "rule-based
// stand-in until the real model exists" shape -- this class is the
// mechanism, the policy of what to do on a shortfall lives in the
// gateway's call site).
//
// No Arduino.h dependency -- host-testable like the rest of sentinel_proto.
// `now_ms` is a parameter everywhere (not millis()) for the same reason
// replay.h and fragment.h take it explicitly: deterministic host tests.

namespace sentinel {

class EnergyBudget {
public:
    // `capacity_j` is the bucket's ceiling (refilling never exceeds it).
    // `refill_rate_j_per_s` is how fast it refills. `initial_j` seeds the
    // starting balance; pass a negative value (the default) to start full.
    EnergyBudget(float capacity_j, float refill_rate_j_per_s, float initial_j = -1.0f);

    // Advances the refill clock to `now_ms`. Safe to call every loop
    // iteration; also called implicitly by can_afford()/spend().
    void tick(uint32_t now_ms);

    // Whether at least `cost_j` is available right now (refills first).
    bool can_afford(float cost_j, uint32_t now_ms);

    // Deducts `cost_j` if affordable and returns true; otherwise leaves
    // the balance untouched and returns false. Refills first, same as
    // can_afford().
    bool spend(float cost_j, uint32_t now_ms);

    // Adds `amount_j` back immediately (e.g. a harvested-energy event or a
    // manual reset for the demo), clamped to capacity.
    void credit(float amount_j);

    float balance_j() const { return balance_j_; }
    float capacity_j() const { return capacity_j_; }
    bool exhausted() const { return balance_j_ <= 0.0f; }

private:
    float capacity_j_;
    float refill_rate_j_per_s_;
    float balance_j_;
    uint32_t last_tick_ms_ = 0;
    bool initialized_ = false;
};

} // namespace sentinel
