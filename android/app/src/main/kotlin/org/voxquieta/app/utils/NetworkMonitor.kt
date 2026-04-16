package org.voxquieta.app.utils

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Singleton that tracks real-time network connectivity.
 *
 * [isOffline] is `true` whenever the device has no active internet connection and
 * updates automatically as the network state changes.  The [ConnectivityManager]
 * callback is registered once for the lifetime of the app process, so no teardown
 * is needed.
 */
@Singleton
class NetworkMonitor @Inject constructor(
    @ApplicationContext context: Context,
) {
    private val connectivityManager = context.getSystemService(ConnectivityManager::class.java)

    private val _isOffline = MutableStateFlow(!isNetworkAvailable())
    val isOffline: StateFlow<Boolean> = _isOffline.asStateFlow()

    private fun isNetworkAvailable(): Boolean {
        val network = connectivityManager.activeNetwork ?: return false
        val caps = connectivityManager.getNetworkCapabilities(network) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    init {
        connectivityManager.registerDefaultNetworkCallback(object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                _isOffline.value = false
            }
            override fun onLost(network: Network) {
                // Only mark offline when there is truly no active network left.
                if (!isNetworkAvailable()) _isOffline.value = true
            }
        })
    }
}
