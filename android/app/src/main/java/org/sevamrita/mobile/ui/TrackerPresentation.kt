package org.sevamrita.mobile.ui

import java.math.BigDecimal

internal data class TrackerStage(val key: String, val label: String, val percent: Double? = null, val assigneeName: String = "") {
    val percentLabel: String get() = percent?.takeIf { it.isFinite() }?.let { "${decimalLabel(it)}%" }.orEmpty()
}

internal data class TrackerDisplay(
    val scale: String, val value: Double? = null, val minimum: Double = 0.0, val maximum: Double = 100.0,
    val unit: String = "", val stage: String = "", val stages: List<TrackerStage> = emptyList()
) {
    val currentIndex: Int get() = stages.indexOfFirst { it.key == stage }
    val milestonePositions: List<Float> get() = stages.mapIndexed { index, step ->
        if (scale == "Stages" && step.percent?.isFinite() == true) (step.percent / 100.0).toFloat().coerceIn(0f, 1f)
        else if (stages.size == 1) 1f else index.toFloat() / (stages.size - 1)
    }
    fun milestoneState(index: Int, outcome: String = "Open"): MilestoneState = when {
        outcome == "Completed" || currentIndex >= 0 && index < currentIndex -> MilestoneState.DONE
        index == currentIndex -> MilestoneState.CURRENT
        else -> MilestoneState.UPCOMING
    }
    val label: String get() = if (scale in listOf("Stages", "Status")) stages.firstOrNull { it.key == stage }?.label ?: "Not started"
        else if (value == null || !value.isFinite()) "Not started"
        else decimalLabel(value) + if (scale == "Percentage") "%" else unit.trim().takeIf { it.isNotBlank() }?.let { " $it" }.orEmpty()
    val fraction: Float? get() = when (scale) {
        "Stages" -> stages.firstOrNull { it.key == stage }?.percent?.takeIf { it.isFinite() }?.let { (it / 100.0).toFloat().coerceIn(0f, 1f) }
        "Status" -> null
        else -> if (value == null || !value.isFinite() || !minimum.isFinite() || !maximum.isFinite() || maximum <= minimum) null
            else ((value - minimum) / (maximum - minimum)).toFloat().coerceIn(0f, 1f)
    }
}

internal enum class MilestoneState { DONE, CURRENT, UPCOMING }

private fun decimalLabel(value: Double) = BigDecimal.valueOf(value).stripTrailingZeros().toPlainString()
