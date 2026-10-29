import type { CrisisResources } from "@/lib/api";

export const crisisFixture: CrisisResources = {
  kind: "self_harm",
  country: "IT",
  country_source: "ip",
  emergency: { number: "112" },
  lines: [
    {
      name: "Telefono Amico",
      phone: "+39 02 2327 2327",
      sms: "+39 324 011 7252",
      hours: "10:00-24:00",
      url: "https://www.telefonoamico.it",
      verified: false,
    },
    {
      name: "Samaritans",
      phone: "(116) 123",
      sms: null,
      hours: null,
      url: null,
      verified: false,
    },
  ],
  international_url: "https://findahelpline.com",
  available_countries: ["AR", "AT", "IT", "US"],
};
