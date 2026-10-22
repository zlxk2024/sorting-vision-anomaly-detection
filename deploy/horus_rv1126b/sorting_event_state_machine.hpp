#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

namespace sorting_vision {

enum class ClassId {
    Parcel = 0,
    DrawerOpen = 1,
    DrawerClosed = 2,
    Chute = 3,
    Bag = 4,
};

struct Box {
    float x1 = 0.0f;
    float y1 = 0.0f;
    float x2 = 0.0f;
    float y2 = 0.0f;
};

struct Detection {
    int class_id = -1;
    float score = 0.0f;
    Box box;
};

struct Event {
    std::string type;
    double start_time_s = 0.0;
    double end_time_s = 0.0;
    int drawer_index = -1;
    int chute_index = -1;
    float confidence = 0.0f;
};

struct Config {
    double open_no_drop_delay_s = 0.75;
    double stall_delay_s = 1.20;
    double event_cooldown_s = 1.00;
    float min_score = 0.35f;
    float overlap_threshold = 0.10f;
};

inline float area(const Box& b) {
    return std::max(0.0f, b.x2 - b.x1) * std::max(0.0f, b.y2 - b.y1);
}

inline float intersection_area(const Box& a, const Box& b) {
    const float x1 = std::max(a.x1, b.x1);
    const float y1 = std::max(a.y1, b.y1);
    const float x2 = std::min(a.x2, b.x2);
    const float y2 = std::min(a.y2, b.y2);
    return std::max(0.0f, x2 - x1) * std::max(0.0f, y2 - y1);
}

inline bool overlaps(const Box& object, const Box& region, float threshold) {
    const float object_area = area(object);
    if (object_area <= 0.0f) {
        return false;
    }
    return intersection_area(object, region) / object_area >= threshold;
}

class SortingEventStateMachine {
public:
    explicit SortingEventStateMachine(Config config = Config()) : config_(config) {}

    std::vector<Event> update(const std::vector<Detection>& detections, double now_s) {
        std::vector<Event> events;
        std::vector<Detection> parcels;
        std::vector<Detection> open_drawers;
        std::vector<Detection> chutes;

        for (const Detection& det : detections) {
            if (det.score < config_.min_score) {
                continue;
            }
            if (det.class_id == static_cast<int>(ClassId::Parcel)) {
                parcels.push_back(det);
            } else if (det.class_id == static_cast<int>(ClassId::DrawerOpen)) {
                open_drawers.push_back(det);
            } else if (det.class_id == static_cast<int>(ClassId::Chute)) {
                chutes.push_back(det);
            }
        }

        std::sort(open_drawers.begin(), open_drawers.end(), [](const Detection& a, const Detection& b) {
            return a.box.x1 < b.box.x1;
        });
        std::sort(chutes.begin(), chutes.end(), [](const Detection& a, const Detection& b) {
            return a.box.x1 < b.box.x1;
        });

        update_open_no_drop(open_drawers, parcels, now_s, events);
        update_stall(chutes, parcels, now_s, events);
        update_multi_parcel_candidate(open_drawers, parcels, now_s, events);

        return events;
    }

private:
    struct TimedRegion {
        Box box;
        double first_seen_s = -1.0;
        double last_alarm_s = -1000.0;
    };

    Config config_;
    std::vector<TimedRegion> open_regions_;
    std::vector<TimedRegion> stall_regions_;
    double last_multi_alarm_s_ = -1000.0;

    void update_open_no_drop(
        const std::vector<Detection>& open_drawers,
        const std::vector<Detection>& parcels,
        double now_s,
        std::vector<Event>& events
    ) {
        resize_regions(open_regions_, open_drawers.size());
        for (size_t i = 0; i < open_drawers.size(); ++i) {
            TimedRegion& state = open_regions_[i];
            state.box = open_drawers[i].box;

            const bool parcel_inside = std::any_of(parcels.begin(), parcels.end(), [&](const Detection& parcel) {
                return overlaps(parcel.box, open_drawers[i].box, config_.overlap_threshold);
            });

            if (!parcel_inside) {
                state.first_seen_s = -1.0;
                continue;
            }
            if (state.first_seen_s < 0.0) {
                state.first_seen_s = now_s;
                continue;
            }
            if (now_s - state.first_seen_s >= config_.open_no_drop_delay_s &&
                now_s - state.last_alarm_s >= config_.event_cooldown_s) {
                events.push_back({"open_no_drop", state.first_seen_s, now_s, static_cast<int>(i), -1, 0.80f});
                state.last_alarm_s = now_s;
            }
        }
    }

    void update_stall(
        const std::vector<Detection>& chutes,
        const std::vector<Detection>& parcels,
        double now_s,
        std::vector<Event>& events
    ) {
        resize_regions(stall_regions_, chutes.size());
        for (size_t i = 0; i < chutes.size(); ++i) {
            TimedRegion& state = stall_regions_[i];
            state.box = chutes[i].box;

            const bool parcel_on_chute = std::any_of(parcels.begin(), parcels.end(), [&](const Detection& parcel) {
                return overlaps(parcel.box, chutes[i].box, config_.overlap_threshold);
            });

            if (!parcel_on_chute) {
                state.first_seen_s = -1.0;
                continue;
            }
            if (state.first_seen_s < 0.0) {
                state.first_seen_s = now_s;
                continue;
            }
            if (now_s - state.first_seen_s >= config_.stall_delay_s &&
                now_s - state.last_alarm_s >= config_.event_cooldown_s) {
                events.push_back({"stall_on_chute", state.first_seen_s, now_s, -1, static_cast<int>(i), 0.75f});
                state.last_alarm_s = now_s;
            }
        }
    }

    void update_multi_parcel_candidate(
        const std::vector<Detection>& open_drawers,
        const std::vector<Detection>& parcels,
        double now_s,
        std::vector<Event>& events
    ) {
        if (now_s - last_multi_alarm_s_ < config_.event_cooldown_s) {
            return;
        }
        for (size_t i = 0; i < open_drawers.size(); ++i) {
            int parcel_count = 0;
            for (const Detection& parcel : parcels) {
                if (overlaps(parcel.box, open_drawers[i].box, config_.overlap_threshold)) {
                    parcel_count++;
                }
            }
            if (parcel_count >= 2) {
                events.push_back({"multi_parcel_candidate", now_s, now_s, static_cast<int>(i), -1, 0.70f});
                last_multi_alarm_s_ = now_s;
                return;
            }
        }
    }

    static void resize_regions(std::vector<TimedRegion>& regions, size_t size) {
        if (regions.size() != size) {
            regions.clear();
            regions.resize(size);
        }
    }
};

}  // namespace sorting_vision
