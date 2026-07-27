import annotate_other_five_v7 as pipeline


FIRST_FIVE = {
    "0041_event_18_open_no_drop_t18.00.jpg": [
        ("parcel", 55, 305, 155, 370),
        ("parcel", 407, 330, 485, 416),
        ("drawer_open", 388, 423, 560, 466),
        ("drawer_closed", 195, 382, 345, 428),
        ("chute", 136, 488, 545, 733),
        ("bag", 122, 850, 628, 1178),
    ],
    "0043_event_18_open_no_drop_t18.20.jpg": [
        ("parcel", 112, 320, 231, 393),
        ("parcel", 482, 340, 559, 420),
        ("drawer_open", 468, 422, 642, 467),
        ("drawer_closed", 52, 378, 229, 435),
        ("drawer_closed", 272, 376, 432, 432),
        ("chute", 87, 489, 560, 752),
        ("bag", 121, 886, 630, 1279),
    ],
    "0047_event_18_open_no_drop_t18.60.jpg": [
        ("parcel", 241, 315, 374, 393),
        ("parcel", 653, 333, 719, 420),
        ("drawer_open", 12, 423, 170, 470),
        ("drawer_closed", 213, 379, 375, 436),
        ("drawer_closed", 421, 375, 584, 434),
        ("chute", 75, 488, 549, 758),
        ("bag", 128, 888, 632, 1279),
    ],
    "0052_event_19_slide_abnormal_t19.10.jpg": [
        ("parcel", 374, 324, 526, 452),
        ("drawer_open", 167, 423, 329, 471),
        ("chute", 19, 493, 500, 772),
        ("bag", 75, 898, 560, 1279),
    ],
    "0055_event_19_slide_abnormal_t19.40.jpg": [
        ("parcel", 0, 339, 34, 402),
        ("parcel", 490, 363, 669, 520),
        ("drawer_open", 279, 422, 442, 470),
        ("drawer_closed", 52, 388, 231, 446),
        ("chute", 0, 487, 489, 773),
        ("bag", 58, 897, 546, 1279),
    ],
}


def main() -> None:
    pipeline.OUTPUT = (
        pipeline.ROOT
        / "datasets/sorting_yolo_stage1/m3_prelabels_10/"
        "five_class_all_10_v8_prompt_standard"
    )
    pipeline.ANNOTATIONS = {**FIRST_FIVE, **pipeline.ANNOTATIONS}
    pipeline.main()


if __name__ == "__main__":
    main()
