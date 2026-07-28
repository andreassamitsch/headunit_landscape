package com.metrolist.music.radio.fyt

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Looper
import androidx.core.content.ContextCompat
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import timber.log.Timber

data class FmGeoLocationState(
    val point: FmGeoPoint? = null,
    val status: String = "Standort deaktiviert",
    val permissionGranted: Boolean = false,
    val active: Boolean = false,
)

/** GPS/network location source used only while RTR station matching is enabled. */
object FmGeoLocationProvider {
    private const val TAG = "FmGeoLocation"
    private const val MIN_TIME_MS = 12_000L
    private const val MIN_DISTANCE_METERS = 350f

    private val _state = MutableStateFlow(FmGeoLocationState())
    val state: StateFlow<FmGeoLocationState> = _state.asStateFlow()

    private var appContext: Context? = null
    private var manager: LocationManager? = null
    private var registered = false

    private val listener = object : LocationListener {
        override fun onLocationChanged(location: Location) {
            accept(location, "GPS aktiv")
        }

        @Deprecated("Deprecated in Android")
        override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) = Unit

        override fun onProviderEnabled(provider: String) {
            _state.value = _state.value.copy(status = "Standortanbieter $provider aktiv")
        }

        override fun onProviderDisabled(provider: String) {
            _state.value = _state.value.copy(status = "Standortanbieter $provider deaktiviert")
        }
    }

    fun hasPermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED

    fun start(context: Context) {
        val applicationContext = context.applicationContext
        appContext = applicationContext
        val granted = hasPermission(applicationContext)
        if (!granted) {
            stop()
            _state.value = FmGeoLocationState(status = "Standortberechtigung fehlt", permissionGranted = false)
            return
        }
        if (registered) {
            _state.value = _state.value.copy(permissionGranted = true, active = true)
            return
        }

        val service = applicationContext.getSystemService(Context.LOCATION_SERVICE) as? LocationManager
        if (service == null) {
            _state.value = FmGeoLocationState(status = "Android-Standortdienst nicht verfügbar", permissionGranted = true)
            return
        }
        manager = service
        bestLastKnown(service)?.let { accept(it, "Letzter Standort verfügbar") }

        val providers = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER, LocationManager.PASSIVE_PROVIDER)
            .filter { provider -> runCatching { service.isProviderEnabled(provider) }.getOrDefault(false) }
        if (providers.isEmpty()) {
            _state.value = _state.value.copy(
                status = "GPS/Standort ist am Gerät ausgeschaltet",
                permissionGranted = true,
                active = false,
            )
            return
        }

        var successful = false
        providers.forEach { provider ->
            runCatching {
                service.requestLocationUpdates(provider, MIN_TIME_MS, MIN_DISTANCE_METERS, listener, Looper.getMainLooper())
                successful = true
            }.onFailure { Timber.tag(TAG).w(it, "Could not register provider %s", provider) }
        }
        registered = successful
        _state.value = _state.value.copy(
            status = if (successful) "GPS wartet auf Position …" else "GPS konnte nicht gestartet werden",
            permissionGranted = true,
            active = successful,
        )
    }

    fun stop() {
        if (registered) runCatching { manager?.removeUpdates(listener) }
        registered = false
        manager = null
        _state.value = FmGeoLocationState(
            point = _state.value.point,
            status = "Standort deaktiviert",
            permissionGranted = appContext?.let(::hasPermission) == true,
            active = false,
        )
    }

    fun permissionChanged(context: Context) {
        if (hasPermission(context)) {
            start(context)
        } else {
            stop()
            _state.value = FmGeoLocationState(status = "Standortberechtigung abgelehnt")
        }
    }

    private fun bestLastKnown(manager: LocationManager): Location? =
        listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER, LocationManager.PASSIVE_PROVIDER)
            .mapNotNull { provider -> runCatching { manager.getLastKnownLocation(provider) }.getOrNull() }
            .maxWithOrNull(compareBy<Location> { it.time }.thenBy { if (it.hasAccuracy()) -it.accuracy else Float.NEGATIVE_INFINITY })

    private fun accept(location: Location, status: String) {
        if (!location.latitude.isFinite() || !location.longitude.isFinite()) return
        val incoming = FmGeoPoint(
            latitude = location.latitude,
            longitude = location.longitude,
            accuracyMeters = location.accuracy.takeIf { location.hasAccuracy() } ?: Float.NaN,
            timestamp = location.time,
        )
        val current = _state.value.point
        val better = current == null || incoming.timestamp >= current.timestamp ||
            (incoming.accuracyMeters.isFinite() &&
                (!current.accuracyMeters.isFinite() || incoming.accuracyMeters < current.accuracyMeters))
        if (!better) return
        _state.value = FmGeoLocationState(
            point = incoming,
            status = status,
            permissionGranted = true,
            active = true,
        )
    }
}
