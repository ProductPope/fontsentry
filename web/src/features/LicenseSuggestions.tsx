import type { KnownFont } from "../lib/api";
import { LICENSE_TYPES } from "../lib/registryForm";

// Autocomplete sources for the license form, referenced by the inputs' `list`
// attribute: license types, plus families and owners of detected/catalog fonts.
export function LicenseSuggestions({ knownFonts }: { knownFonts: KnownFont[] }) {
  const owners = [...new Set(knownFonts.map((k) => k.owner).filter((o): o is string => !!o))].sort();
  return (
    <>
      <datalist id="license-types">
        {LICENSE_TYPES.map((t) => (
          <option key={t} value={t} />
        ))}
      </datalist>
      <datalist id="known-families">
        {knownFonts.map((k) => (
          <option key={k.family} value={k.family} />
        ))}
      </datalist>
      <datalist id="known-owners">
        {owners.map((o) => (
          <option key={o} value={o} />
        ))}
      </datalist>
    </>
  );
}
