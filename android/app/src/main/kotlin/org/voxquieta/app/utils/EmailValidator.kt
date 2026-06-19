package org.voxquieta.app.utils

/**
 * Lightweight, framework-free email validation.
 *
 * Deliberately uses a plain regex rather than `android.util.Patterns.EMAIL_ADDRESS`
 * so the rule can be unit-tested on the JVM without Robolectric. This is a pragmatic
 * "looks like an email" check used to keep the user out of a guaranteed server-side
 * 422; the backend's `EmailStr` validator remains the source of truth.
 */
private val EMAIL_REGEX = Regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")

/** Returns true when [value] (trimmed) looks like a valid email address. */
fun isValidEmail(value: String): Boolean = EMAIL_REGEX.matches(value.trim())
