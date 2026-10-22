// Integration skeleton for Horus RV1126B.
//
// This file is intentionally small and focused. It shows where the trained
// sorting YOLO RKNN output should enter the anomaly state machine. The final
// product should merge this structure into the vendor SDK example:
//
//   sdk/src/example/obj_detection_yolov8_1126b.cpp
//
// Keep vendor frame acquisition, RKNN init/run, and OSD/WebSocket code there.

#include "sorting_event_state_machine.hpp"

#include <cstdio>
#include <string>
#include <vector>

namespace {

using sorting_vision::Box;
using sorting_vision::Config;
using sorting_vision::Detection;
using sorting_vision::Event;
using sorting_vision::SortingEventStateMachine;

const char* class_name(int class_id) {
    switch (class_id) {
        case 0:
            return "parcel";
        case 1:
            return "drawer_open";
        case 2:
            return "drawer_closed";
        case 3:
            return "chute";
        case 4:
            return "bag";
        default:
            return "unknown";
    }
}

void push_alarm_event(const Event& event) {
    // Replace this with the actual Horus output path:
    // - ws_detect_result_push for WebSocket
    // - TCP/HTTP report to server
    // - GPIO/RS485 for alarm light
    std::printf(
        "{\"event_type\":\"%s\",\"start_time_s\":%.3f,\"end_time_s\":%.3f,"
        "\"drawer_index\":%d,\"chute_index\":%d,\"confidence\":%.2f}\n",
        event.type.c_str(),
        event.start_time_s,
        event.end_time_s,
        event.drawer_index,
        event.chute_index,
        event.confidence
    );
}

}  // namespace

int main() {
    Config config;
    config.open_no_drop_delay_s = 0.75;
    config.stall_delay_s = 1.20;
    config.event_cooldown_s = 1.00;
    config.min_score = 0.35f;

    SortingEventStateMachine state_machine(config);

    // In the real Horus app, this loop is driven by:
    //
    //   HRS_VideoGetFrame(...)
    //   rknn_inputs_set(...)
    //   rknn_run(...)
    //   rknn_outputs_get(...)
    //   YOLO11 postprocess
    //
    // Then convert YOLO results into Detection objects and call update().
    std::vector<Detection> detections = {
        {1, 0.88f, Box{100.0f, 100.0f, 220.0f, 150.0f}},
        {0, 0.91f, Box{130.0f, 105.0f, 180.0f, 145.0f}},
        {3, 0.95f, Box{90.0f, 170.0f, 260.0f, 360.0f}},
    };

    for (double t = 0.0; t < 2.0; t += 0.2) {
        std::vector<Event> events = state_machine.update(detections, t);
        for (const Event& event : events) {
            push_alarm_event(event);
        }
    }

    for (const Detection& detection : detections) {
        std::printf(
            "detected %s score=%.2f box=(%.1f %.1f %.1f %.1f)\n",
            class_name(detection.class_id),
            detection.score,
            detection.box.x1,
            detection.box.y1,
            detection.box.x2,
            detection.box.y2
        );
    }

    return 0;
}
