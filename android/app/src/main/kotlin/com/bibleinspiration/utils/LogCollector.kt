package com.bibleinspiration.utils

import timber.log.Timber
import java.util.concurrent.CopyOnWriteArrayList

/**
 * A Timber Tree that keeps the last [maxEntries] log lines in memory.
 * Plant it once in [com.bibleinspiration.BibleInspirationApp.onCreate] (both debug AND release
 * builds, since we want logs available for bug reports in release too).
 */
object LogCollector : Timber.Tree() {

    private const val maxEntries = 500
    private val entries = CopyOnWriteArrayList<String>()

    override fun log(priority: Int, tag: String?, message: String, t: Throwable?) {
        val priorityChar = when (priority) {
            android.util.Log.VERBOSE -> 'V'
            android.util.Log.DEBUG   -> 'D'
            android.util.Log.INFO    -> 'I'
            android.util.Log.WARN    -> 'W'
            android.util.Log.ERROR   -> 'E'
            else                     -> '?'
        }
        val line = "$priorityChar/${tag ?: "App"}: $message" +
            (t?.let { "\n${it.stackTraceToString()}" } ?: "")
        if (entries.size >= maxEntries) entries.removeAt(0)
        entries.add(line)
    }

    fun getLog(): String = entries.joinToString("\n")

    fun clear() { entries.clear() }
}
