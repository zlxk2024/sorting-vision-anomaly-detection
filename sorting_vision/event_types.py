"""Business event names. Stable IDs keep existing consumers and records compatible."""

DEFAULT_EVENT_TYPES = ('wrong_chute', 'multi_parcel_drawer', 'chute_stall')
EVENT_NAMES = {
    'wrong_chute': '落格错误',
    'multi_parcel_drawer': '一车两件/多件混放',
    'chute_stall': '格口包裹滞留',
    # Historical records and internal legacy rules only; disabled by default.
    'open_no_drop': '不掉件',
}
