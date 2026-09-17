"""Constants for FortiOS-KD."""

DOMAIN = "fortios_kd"
DATA_FILTER_MANAGER = "filter_manager"

DEFAULT_VERIFY_SSL = True

CONF_ORGANIZATION_MODE = "organization_mode"
ORGANIZATION_MODE_NONE = "none"
ORGANIZATION_MODE_AREA = "area"
ORGANIZATION_MODE_LABEL = "label"
ORGANIZATION_MODE_BOTH = "both"
DEFAULT_ORGANIZATION_MODE = ORGANIZATION_MODE_NONE

CONF_HUB_AREA_ID = "hub_area_id"
CONF_NEW_HUB_AREA_NAME = "new_hub_area_name"
CONF_INHERIT_HUB_AREA = "inherit_hub_area"
DEFAULT_INHERIT_HUB_AREA = False
CONF_MOVE_DEVICES_WITH_HUB = "move_devices_if_hub_moves"
DEFAULT_MOVE_DEVICES_WITH_HUB = False
CONF_CLIENTS_FOLLOW_AP_AREA = "clients_follow_ap_area"
DEFAULT_CLIENTS_FOLLOW_AP_AREA = False
CONF_CLIENTS_FOLLOW_AP_LABELS = "clients_follow_ap_labels"
DEFAULT_CLIENTS_FOLLOW_AP_LABELS = False
CONF_DEVICES_FOLLOW_HUB_LABELS = "devices_follow_hub_labels"
DEFAULT_DEVICES_FOLLOW_HUB_LABELS = False

CONF_HUB_LABEL = "hub_label"
CONF_HUB_LABEL_ID = "hub_label_id"
CONF_NEW_HUB_LABEL_NAME = "new_hub_label_name"
CONF_HUB_LABEL_COLOR = "hub_label_color"
DEFAULT_HUB_LABEL_COLOR = [3, 169, 244]

CONF_REQUEST_TIMEOUT = "request_timeout"
DEFAULT_REQUEST_TIMEOUT = 60

CONF_INCLUDE_UNASSIGNED_SSIDS = "include_unassigned_ssids"
DEFAULT_INCLUDE_UNASSIGNED_SSIDS = False

CONF_SYNC_ARP_TABLE = "sync_arp_table"
DEFAULT_SYNC_ARP_TABLE = False
CONF_MATCH_ARP_WIFI_CLIENTS = "match_arp_wifi_clients"
DEFAULT_MATCH_ARP_WIFI_CLIENTS = True

RADIO_SPECTRUM_BANDS = {
    "24ghz": "2.4 GHz",
    "5ghz": "5 GHz",
    "6ghz": "6 GHz",
}

# Used when a FortiGate cannot provide monitor/wifi/meta. The runtime mapping
# returned by the FortiGate is authoritative and overrides these values.
RADIO_TYPE_BANDS = {
    "802.11b": "2.4 GHz",
    "802.11g": "2.4 GHz",
    "802.11g-only": "2.4 GHz",
    "802.11n": "2.4 GHz",
    "802.11n,g-only": "2.4 GHz",
    "802.11n-only": "2.4 GHz",
    "802.11ax": "2.4 GHz",
    "802.11ax,n-only": "2.4 GHz",
    "802.11ax,n,g-only": "2.4 GHz",
    "802.11ax-only": "2.4 GHz",
    "802.11a": "5 GHz",
    "802.11n-5G": "5 GHz",
    "802.11n-5G-only": "5 GHz",
    "802.11ac": "5 GHz",
    "802.11ac-2G": "2.4 GHz",
    "802.11ac,n-only": "5 GHz",
    "802.11ac-only": "5 GHz",
    "802.11ax-5G": "5 GHz",
    "802.11ax,ac,n-only": "5 GHz",
    "802.11ax,ac-only": "5 GHz",
    "802.11ax-5G-only": "5 GHz",
}

CONF_MASK_SERIAL_NUMBERS = "mask_serial_numbers"
DEFAULT_MASK_SERIAL_NUMBERS = True
CONF_MASK_SSIDS = "mask_ssids"
DEFAULT_MASK_SSIDS = True
CONF_MASK_CLIENT_MACS = "mask_client_macs"
DEFAULT_MASK_CLIENT_MACS = True

CONF_MASK_CLIENT_HOSTNAMES = "mask_client_hostnames"
DEFAULT_MASK_CLIENT_HOSTNAMES = True

CONF_MASK_VLAN_IDS = "mask_vlan_ids"
DEFAULT_MASK_VLAN_IDS = True

CONF_MASK_AP_NAMES = "mask_ap_names"
DEFAULT_MASK_AP_NAMES = True
