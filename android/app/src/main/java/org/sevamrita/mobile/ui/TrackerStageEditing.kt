package org.sevamrita.mobile.ui

/** Stage keys are stable: inserting a row must not change the current step or its history. */
internal fun insertTrackerStage(
    stages: List<TrackerStage>, afterKey: String?, added: TrackerStage, scale: String
): List<TrackerStage> {
    require(scale in listOf("Status", "Stages")) { "This tracker does not use stages or statuses." }
    require(stages.size < 30) { "A tracker can have at most 30 stages or statuses." }
    require(added.key.isNotBlank() && stages.none { it.key == added.key }) { "Choose a distinct stage identifier." }
    val index = if (afterKey == null && stages.isEmpty()) -1 else stages.indexOfFirst { it.key == afterKey }
    require(index >= 0 || stages.isEmpty() && afterKey == null) { "The selected stage is unavailable. Reopen the tracker." }
    if (scale == "Status") return stages.toMutableList().apply { add(index + 1, added.copy(percent = null)) }
    require(stages.map { it.percent }.all { it != null && it.isFinite() && it in 0.0..100.0 } &&
        stages.zipWithNext().all { (left, right) -> left.percent!! < right.percent!! }) { "Stage percentages must increase within 0–100." }
    val rows = stages.toMutableList()
    var position = 100.0
    if (index < rows.lastIndex) {
        val left = rows[index].percent!!
        val right = rows[index + 1].percent!!
        position = left + (right - left) / 2.0
    } else if (index >= 0 && rows[index].percent == 100.0) {
        val previous = rows.getOrNull(index - 1)?.percent ?: 0.0
        rows[index] = rows[index].copy(percent = previous + (100.0 - previous) / 2.0)
    }
    rows.add(index + 1, added.copy(percent = position))
    // Very tightly spaced legacy percentages can have no representable midpoint.
    if (!rows.zipWithNext().all { (left, right) -> left.percent!! < right.percent!! })
        return rows.mapIndexed { i, stage -> stage.copy(percent = (i + 1) * 100.0 / rows.size) }
    return rows
}

internal fun editTrackerStage(stages: List<TrackerStage>, key: String, label: String, person: String, personName: String): List<TrackerStage> {
    require(stages.any { it.key == key }) { "The selected stage is unavailable. Reopen the tracker." }
    require(label.isNotBlank() && label.trim().length <= 100) { "Enter a stage name of up to 100 characters." }
    return stages.map { if (it.key == key) it.copy(label = label.trim(), assigneeUser = person, assigneeName = personName) else it }
}
