package org.voxquieta.app

import android.content.Context
import android.content.ContextWrapper
import android.content.res.Configuration
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import org.voxquieta.app.analytics.AnalyticsHelper
import org.voxquieta.app.presentation.screens.ChatScreen
import org.voxquieta.app.presentation.screens.ConversationsScreen
import org.voxquieta.app.presentation.screens.SettingsScreen
import org.voxquieta.app.presentation.screens.SplashScreen
import org.voxquieta.app.presentation.theme.VoxQuietaTheme
import org.voxquieta.app.presentation.viewmodels.ChatViewModel
import org.voxquieta.app.utils.LocaleHelper
import dagger.hilt.android.AndroidEntryPoint
import java.util.Locale
import javax.inject.Inject

private fun Context.hasSplashBeenSeen(): Boolean =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .getBoolean("splash_seen", false)

private fun Context.markSplashSeen() =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .edit().putBoolean("splash_seen", true).apply()

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var analyticsHelper: AnalyticsHelper

    override fun onCreate(savedInstanceState: Bundle?) {
        // Install the AndroidX Splash Screen before super.onCreate() so the
        // splash window is shown immediately from the very first frame.
        installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Log the app_open event on every cold start.
        analyticsHelper.logEvent(AnalyticsHelper.EVENT_APP_OPEN)

        setContent {
            val viewModel: ChatViewModel = hiltViewModel()
            val uiState by viewModel.uiState.collectAsState()
            val languageCode by viewModel.selectedLanguage.collectAsStateWithLifecycle()

            val layoutDirection = LocaleHelper.layoutDirectionFor(languageCode)

            val darkTheme = when (uiState.themeMode) {
                "dark" -> true
                "light" -> false
                else -> isSystemInDarkTheme()
            }

            // Build a locale-aware Configuration AND a locale-aware Context so that all
            // stringResource() calls inside the composition tree resolve strings from the
            // correct locale's strings.xml without requiring an Activity restart.
            //
            // We provide BOTH LocalConfiguration and LocalContext:
            //   - LocalConfiguration: used by Material3 / Compose internals for layout metrics.
            //   - LocalContext: used by stringResource() to look up string resources; we wrap
            //     it with createConfigurationContext() so the Resources object uses the new locale.
            //
            // IMPORTANT — Activity context preservation:
            // hiltViewModel() (via hilt-navigation-compose) calls LocalContext.current and then
            // walks the ContextWrapper chain looking for a ComponentActivity via findActivity().
            // createConfigurationContext() wraps the Activity's *baseContext* (not the Activity
            // itself), which breaks that walk.  We therefore create the localized context by
            // wrapping the Activity directly, so the chain is:
            //   LocalizedActivityContext → Activity → ...
            // This keeps hiltViewModel() working in every NavHost destination.
            val activity = LocalContext.current
            val localizedConfiguration = remember(languageCode) {
                val locale = Locale(languageCode)
                Configuration(activity.resources.configuration).also { cfg ->
                    cfg.setLocale(locale)
                }
            }
            // Wrap the Activity (not its baseContext) so the ContextWrapper chain still
            // contains the ComponentActivity that hiltViewModel() needs.
            val localizedContext: Context = remember(languageCode) {
                object : ContextWrapper(activity) {
                    private val localizedResources = activity.createConfigurationContext(localizedConfiguration).resources
                    override fun getResources() = localizedResources
                }
            }

            VoxQuietaTheme(darkTheme = darkTheme) {
                CompositionLocalProvider(
                    LocalLayoutDirection provides layoutDirection,
                    LocalConfiguration provides localizedConfiguration,
                    LocalContext provides localizedContext,
                ) {
                    val navController = rememberNavController()

                    // Track screen views every time the user navigates to a new destination.
                    remember(navController) {
                        navController.addOnDestinationChangedListener(
                            object : NavController.OnDestinationChangedListener {
                                override fun onDestinationChanged(
                                    controller: NavController,
                                    destination: androidx.navigation.NavDestination,
                                    arguments: Bundle?,
                                ) {
                                    // Strip route args so "chat/{conversationId}" → "chat"
                                    val screenName = destination.route
                                        ?.substringBefore("/")
                                        ?: destination.displayName
                                    analyticsHelper.setCurrentScreen(screenName)
                                }
                            },
                        )
                    }

                    val startDestination = remember {
                        if (localizedContext.hasSplashBeenSeen()) "conversations" else "splash"
                    }

                    NavHost(
                        navController = navController,
                        startDestination = startDestination,
                    ) {
                        composable("splash") {
                            SplashScreen(
                                onComplete = {
                                    localizedContext.markSplashSeen()
                                    navController.navigate("conversations") {
                                        popUpTo("splash") { inclusive = true }
                                    }
                                },
                            )
                        }
                        composable("conversations") {
                            ConversationsScreen(
                                onNewConversation = { navController.navigate("chat/new") },
                                onSelectConversation = { id -> navController.navigate("chat/$id") },
                                onOpenSettings = { navController.navigate("settings") },
                            )
                        }
                        composable("chat/{conversationId}") { backStackEntry ->
                            val conversationId = backStackEntry.arguments?.getString("conversationId")
                            ChatScreen(
                                conversationId = conversationId,
                                onOpenSettings = { navController.navigate("settings") },
                            )
                        }
                        composable("settings") {
                            SettingsScreen(
                                onNavigateBack = { navController.popBackStack() },
                            )
                        }
                    }
                }
            }
        }
    }
}
