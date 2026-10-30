package org.voxquieta.app.testing

import org.voxquieta.app.domain.models.CrisisLine
import org.voxquieta.app.domain.models.CrisisResources

/** Shared BITB-255 crisis card fixture (an Italian turn resolved from the IP country). */
val crisisFixture = CrisisResources(
    kind = "self_harm",
    country = "IT",
    countrySource = "ip",
    emergencyNumber = "112",
    lines = listOf(
        CrisisLine(
            name = "Telefono Amico",
            phone = "+39 02 2327 2327",
            sms = "+39 324 011 7252",
            hours = "10:00-24:00",
            url = "https://www.telefonoamico.it",
        ),
        CrisisLine(name = "Samaritans", phone = "(116) 123"),
    ),
    internationalUrl = "https://findahelpline.com",
    availableCountries = listOf("AT", "IT", "US"),
)

/** The wire JSON the backend streams for [crisisFixture]. */
const val CRISIS_EVENT_JSON =
    """{"type":"crisis_resources","resources":{"kind":"self_harm","country":"IT","country_source":"ip",""" +
        """"emergency":{"number":"112"},"lines":[{"name":"Telefono Amico","phone":"+39 02 2327 2327",""" +
        """"sms":"+39 324 011 7252","hours":"10:00-24:00","url":"https://www.telefonoamico.it","verified":false},""" +
        """{"name":"Samaritans","phone":"(116) 123","sms":null,"hours":null,"url":null,"verified":false}],""" +
        """"international_url":"https://findahelpline.com","available_countries":["AT","IT","US"]}}"""
