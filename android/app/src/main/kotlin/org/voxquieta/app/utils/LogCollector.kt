package org.voxquieta.app.utils

import java.util.concurrent.CopyOnWriteArrayList

/**
 * Pure-Kotlin in-memory log ring-buffer.
 *
 * Keeps the last [maxEntries] log lines so they can be exported for bug reports.
 * Deliberately has no dependency on Timber or android.util.Log so it is safe
 * to use in JVM unit tests without testOptions.unitTests.returnDefaultValues.
 *
 * Plant it as a Timber tree from [org.voxquieta.app.VoxQuietaApp.onCreate]:
 * ```
 * Timber.plant(object : Timber.Tree() {
 *     override fun log(priority: Int, tag: String?, message: String, t: Throwable?) =
 *         LogCollector.log(priority, tag, message, t)
 * })
 * ```
 *
 * Priority int values match android.util.Log constants:
 *   VERBOSE=2, DEBUG=3, INFO=4, WARN=5, ERROR=6
 */
object LogCollector {

    private const val maxEntries = 500
    private val entries = CopyOnWriteArrayList<String>()

    fun log(priority: Int, tag: String?, message: String, t: Throwable?) {
        val priorityChar = when (priority) {
            2    -> 'V' // VERBOSE
            3    -> 'D' // DEBUG
            4    -> 'I' // INFO
            5    -> 'W' // WARN
            6    -> 'E' // ERROR
            else -> '?'
        }
        val line = "$priorityChar/${tag ?: "App"}: $message" +
            (t?.let { "\n${it.stackTraceToString()}" } ?: "")
        if (entries.size >= maxEntries) entries.removeAt(0)
        entries.add(line)
    }

    fun getLog(): String = entries.joinToString("\n")

    fun clear() { entries.clear() }
}
