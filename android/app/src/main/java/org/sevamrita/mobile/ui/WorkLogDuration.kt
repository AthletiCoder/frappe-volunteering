package org.sevamrita.mobile.ui

import java.math.BigDecimal
import java.math.RoundingMode

internal fun workLogMinutes(hours: String): Int? = runCatching {
    val value = hours.toBigDecimalOrNull() ?: return null
    if (value < BigDecimal.ZERO) return null
    value.multiply(BigDecimal(60)).setScale(0, RoundingMode.HALF_UP).intValueExact()
}.getOrNull()

internal fun workLogDurationHours(hours: Int, minutes: Int): String {
    require(hours in 0..24 && minutes in 0..59 && (hours < 24 || minutes == 0))
    return BigDecimal(hours * 60 + minutes).divide(BigDecimal(60), 9, RoundingMode.HALF_UP)
        .stripTrailingZeros().toPlainString()
}

internal fun workLogDurationLabel(hours: String): String {
    val minutes = workLogMinutes(hours) ?: return "0 min"
    return listOfNotNull((minutes / 60).takeIf { it > 0 }?.let { "$it h" },
        (minutes % 60).takeIf { it > 0 || minutes == 0 }?.let { "$it min" }).joinToString(" ")
}

internal fun workLogTitle(team: Boolean) = if (team) "Team work log" else "My work log"

internal fun workLogDetails(description: String, legacyLink: String): String {
    val link = legacyLink.trim()
    return if (link.isBlank() || description.contains(link)) description
    else listOf(description, link).filter(String::isNotEmpty).joinToString("\n\n")
}
