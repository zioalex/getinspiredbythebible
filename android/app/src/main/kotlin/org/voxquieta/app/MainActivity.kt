package org.voxquieta.app

import android.content.Context
import android.os.Bundle
import android.os.SystemClock
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import org.voxquieta.app.analytics.AnalyticsHelper
import org.voxquieta.app.presentation.components.TurnstileWebView
import org.voxquieta.app.presentation.screens.ChangelogScreen
import org.voxquieta.app.presentation.screens.ChatScreen
import org.voxquieta.app.presentation.screens.ConversationsScreen
import org.voxquieta.app.presentation.screens.SettingsScreen
import org.voxquieta.app.presentation.screens.SplashScreen
import org.voxquieta.app.presentation.theme.VoxQuietaTheme
import org.voxquieta.app.presentation.viewmodels.ChatViewModel
import org.voxquieta.app.security.TurnstileManager
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CancellationException
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

    // Accessed before setContent{} to drive setKeepOnScreenCondition.
    // hiltViewModel() inside setContent{} returns the same Activity-scoped instance.
    private val viewModel: ChatViewModel by viewModels()

    // Mounted globally below in setContent so the Cloudflare Turnstile widget
    // pre-warms during splash/conversations and any first POST (chat, church
    // search, feedback) finds a token already cached.
    @Inject
    lateinit var turnstileManager: TurnstileManager

    override fun onCreate(savedInstanceState: Bundle?) {
        // Capture the splash screen handle before super.onCreate() as required by the API.
        val splashScreen = installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Keep the system splash on screen until the backend has responded (translations
        // loaded) OR the device is offline, but cap at 700 ms so fast devices get a
        // deliberate beat rather than an instant flash.  The 700 ms windowSplashScreen-
        // AnimationDuration in themes.xml is the minimum; this condition can dismiss
        // earlier once the backend is ready.
        val splashStartMs = SystemClock.elapsedRealtime()
        splashScreen.setKeepOnScreenCondition {
            val elapsed = SystemClock.elapsedRealtime() - splashStartMs
            val backendReady = viewModel.availableTranslations.value.isNotEmpty()
                    || viewModel.uiState.value.isOffline
            elapsed < 700L && !backendReady
        }

        // Log app_open only on a genuine cold start, not on Activity recreations
        // triggered by locale changes (AppCompatDelegate.setApplicationLocales recreates
        // the Activity on SDK < 33), rotation, or other config changes.
        if (savedInstanceState == null) {
            analyticsHelper.logEvent(AnalyticsHelper.EVENT_APP_OPEN)
        }

        setContent {
            val viewModel: ChatViewModel = hiltViewModel()
            val uiState by viewModel.uiState.collectAsState()

            val darkTheme = when (uiState.themeMode) {
                "dark" -> true
                "light" -> false
                else -> isSystemInDarkTheme()
            }

            // Locale handling lives at the system level: the picker calls
            // ChatViewModel.setLocale(...) -> LocaleApplier.apply(...) ->
            // AppCompatDelegate.setApplicationLocales(...). The platform recreates this
            // Activity with the new Configuration, so stringResource() and the layout
            // direction (RTL for Arabic) just work without per-composition wrapping.
            VoxQuietaTheme(darkTheme = darkTheme) {
                val navController = rememberNavController()
                val context = LocalContext.current

                // Track screen views every time the user navigates to a new destination.
                DisposableEffect(navController) {
                    val listener = NavController.OnDestinationChangedListener { _, destination, _ ->
                        // Strip route args so "chat/{conversationId}" → "chat"
                        val screenName = destination.route
                            ?.substringBefore("/")
                            ?: "unknown"
                        analyticsHelper.setCurrentScreen(screenName)
                    }
                    navController.addOnDestinationChangedListener(listener)
                    onDispose {
                        navController.removeOnDestinationChangedListener(listener)
                    }
                }

                // Single start destination: the splash route resolves the last
                // conversation (or creates a new one) and replaces itself with
                // chat/{id} so Back from chat exits the app instead of returning
                // here.
                val startDestination = remember {
                    if (context.hasSplashBeenSeen()) "resume" else "splash"
                }

                // Paint the themed background across the whole screen so no route
                // (notably the async "resume" resolver) ever exposes the white
                // window background. Uses `background` to match the post-splash
                // windowBackground and the chat Scaffold for a seamless transition.
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                Box {
                    NavHost(
                        navController = navController,
                        startDestination = startDestination,
                    ) {
                        composable("splash") {
                            SplashScreen(
                                onComplete = {
                                    context.markSplashSeen()
                                    navController.navigate("resume") {
                                        popUpTo("splash") { inclusive = true }
                                    }
                                },
                            )
                        }
                        composable("resume") {
                            // Tiny resolver: looks up the last conversation id and
                            // replaces itself with the appropriate chat route. The DB
                            // query is async, so this route would otherwise render
                            // nothing — and the post-splash window background is white
                            // (Theme.VoxQuieta = Material.Light), producing the blank
                            // white screen reported on resume from a reclaimed task.
                            // Show a loading indicator over the themed surface so the
                            // user always sees intentional content, never a blank void.
                            val resumeViewModel: ChatViewModel = hiltViewModel()
                            LaunchedEffect(Unit) {
                                val target = try {
                                    val id = resumeViewModel.resolveResumeConversationId()
                                    if (id != null) "chat/$id" else "chat/new"
                                } catch (e: Exception) {
                                    if (e is CancellationException) throw e
                                    "chat/new"
                                }
                                navController.navigate(target) {
                                    popUpTo("resume") { inclusive = true }
                                }
                            }
                            Box(
                                modifier = Modifier.fillMaxSize(),
                                contentAlignment = Alignment.Center,
                            ) {
                                CircularProgressIndicator()
                            }
                        }
                        composable("conversations") {
                            ConversationsScreen(
                                onNewConversation = {
                                    navController.navigate("chat/new") {
                                        popUpTo("conversations") { inclusive = true }
                                    }
                                },
                                onSelectConversation = { id ->
                                    navController.navigate("chat/$id") {
                                        popUpTo("conversations") { inclusive = true }
                                    }
                                },
                                onOpenSettings = { navController.navigate("settings") },
                                onNavigateBack = { navController.popBackStack() },
                            )
                        }
                        composable("chat/{conversationId}") { backStackEntry ->
                            val conversationId = backStackEntry.arguments?.getString("conversationId")
                            ChatScreen(
                                conversationId = conversationId,
                                onOpenSettings = { navController.navigate("settings") },
                                onOpenAllConversations = { navController.navigate("conversations") },
                                onSelectConversation = { id ->
                                    navController.navigate("chat/$id") {
                                        // Replace current chat in the back stack so Back exits
                                        // the app rather than walking through every prior chat.
                                        popUpTo("chat/{conversationId}") { inclusive = true }
                                    }
                                },
                                onNewConversation = {
                                    navController.navigate("chat/new") {
                                        popUpTo("chat/{conversationId}") { inclusive = true }
                                    }
                                },
                            )
                        }
                        composable("settings") {
                            SettingsScreen(
                                onNavigateBack = { navController.popBackStack() },
                                onOpenChangelog = { navController.navigate("changelog") },
                            )
                        }
                        composable("changelog") {
                            ChangelogScreen(
                                onNavigateBack = { navController.popBackStack() },
                            )
                        }
                    }

                    // Activity-scoped Turnstile widget. Stays mounted for the
                    // life of the activity so any first POST request (regardless
                    // of which screen the user navigates to first) finds a fresh
                    // token already cached. The widget itself is 1.dp / invisible.
                    TurnstileWebView(turnstileManager = turnstileManager)
                }
                } // Surface
            }
        }
    }
}
