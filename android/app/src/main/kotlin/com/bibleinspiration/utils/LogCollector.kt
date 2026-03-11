package com.bibleinspiration.utils

import timber.log.Timber
import java.util.concurrent.CopyOnWriteArrayList

/**
 * A Timber Tree that keeps the last [maxEntries] log lines in memory.
 * Plant it once in [com.bibleinspiration.BibleInspirationApp.onCreate] (both debug AND release
 * builds, since we want logs available for bug reports in release too).
 *
 * Priority int values match android.util.Log constants (avoid importing Log to satisfy UseTimber lint rule):
 *   VERBOSE=2, DEBUG=3, INFO=4, WARN=5, ERROR=6
 */
object LogCollector : Timber.Tree() {

    private const val maxEntries = 500
    private val entries = CopyOnWriteArrayList<String>()

    override fun log(priority: Int, tag: String?, message: String, t: Throwable?) {
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
