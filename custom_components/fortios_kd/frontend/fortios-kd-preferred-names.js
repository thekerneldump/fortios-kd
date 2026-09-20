const PREFERRED_NAME_SCOPE_ATTRIBUTE = "fortios_kd_preferred_name_scope";
const UNAVAILABLE_STATES = new Set(["unknown", "unavailable", ""]);

function registryEntry(registry, id) {
  return registry?.get?.(id) ?? registry?.[id];
}

export function preferredNamesByDevice(hass, scope = "fortigate") {
  const names = new Map();

  for (const state of Object.values(hass.states)) {
    if (
      state.attributes[PREFERRED_NAME_SCOPE_ATTRIBUTE] !== scope ||
      UNAVAILABLE_STATES.has(state.state)
    ) {
      continue;
    }

    const entity = registryEntry(hass.entities, state.entity_id);
    const preferredName = state.state.trim();
    if (entity?.device_id && preferredName) {
      names.set(entity.device_id, preferredName);
    }
  }

  return names;
}

export function preferredDeviceName(
  preferredNames,
  device,
  fallback = "",
) {
  return (
    (device?.id && preferredNames.get(device.id)) ||
    device?.name_by_user ||
    device?.name ||
    fallback
  );
}
