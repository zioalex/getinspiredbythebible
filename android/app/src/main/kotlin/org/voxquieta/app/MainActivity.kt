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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.material3.Surface
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import org.voxquieta.app.analytics.AnalyticsHelper
import org.voxquieta.app.presentation.components.TurnstileWebView
import org.voxquieta.app.presentation.components.WhatsNewBottomSheet
import org.voxquieta.app.presentation.components.shouldShowWhatsNew
import org.voxquieta.app.presentation.screens.ChangelogScreen
import org.voxquieta.app.presentation.screens.ChatScreen
import org.voxquieta.app.presentation.screens.ConversationsScreen
import org.voxquieta.app.presentation.screens.SettingsScreen
import org.voxquieta.app.presentation.screens.SplashScreen
import org.voxquieta.app.presentation.theme.VoxQuietaTheme
import org.voxquieta.app.presentation.viewmodels.ChatViewModel
import org.voxquieta.app.security.TurnstileManager
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

private fun Context.hasSplashBeenSeen(): Boolean =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .getBoolean("splash_seen", false)

private fun Context.markSplashSeen() =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .edit().putBoolean("splash_seen", true).apply()

private fun Context.lastSeenVersionCode(): Int =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .getInt("last_seen_version_code", -1)

private fun Context.markVersionSeen(code: Int) =
    getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        .edit().putInt("last_seen_version_code", code).apply()

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

    // Play In-App Update (BITB-057): flexible flow, checked on cold start and on resume.
    @Inject
    lateinit var inAppUpdateManager: InAppUpdateManager

    // Computed once on cold start (BITB-058); read inside setContent{} to seed the
    // "What's New" sheet's Compose state.
    private var showWhatsNewOnLaunch = false

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

            // "What's New" bottom sheet (BITB-058): shown once per update, never on
            // fresh install. The version is marked seen here (not on dismiss/see-all)
            // so a process death before the user acts still counts as "seen".
            val storedVersion = lastSeenVersionCode()
            showWhatsNewOnLaunch = shouldShowWhatsNew(storedVersion, BuildConfig.VERSION_CODE)
            if (storedVersion != BuildConfig.VERSION_CODE) markVersionSeen(BuildConfig.VERSION_CODE)
        }

        // Play Store isn't available in debug builds, so the check is a silent no-op there.
        if (!BuildConfig.DEBUG) inAppUpdateManager.checkForUpdate(this)

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
                var showWhatsNew by remember { mutableStateOf(showWhatsNewOnLaunch) }

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
                            // Always open a fresh chat on launch (BITB-049). Conversation
                            // history remains reachable via the drawer. Navigation is
                            // synchronous so no loading indicator is needed.
                            // resolveResumeConversationId() / LastConversationPreferences
                            // are kept for a future opt-in "resume last chat" setting.
                            LaunchedEffect(Unit) {
                                navController.navigate("chat/new") {
                                    popUpTo("resume") { inclusive = true }
                                }
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

                    // "What's New" bottom sheet (BITB-058). Version is already marked
                    // seen in onCreate, so both actions just dismiss the overlay.
                    if (showWhatsNew) {
                        WhatsNewBottomSheet(
                            onDismiss = { showWhatsNew = false },
                            onSeeAll = {
                                showWhatsNew = false
                                navController.navigate("changelog")
                            },
                        )
                    }

                    // Activity-scoped snackbar for the in-app update flow (BITB-057).
                    // There's no single reusable SnackbarHost in this Compose tree
                    // (ChatScreen owns its own, scoped to its Scaffold), so the update
                    // prompt gets its own top-level host here.
                    val updateSnackbarHostState = remember { SnackbarHostState() }
                    val installMessage = stringResource(id = R.string.update_downloaded_message)
                    val installAction = stringResource(id = R.string.update_install_action)
                    LaunchedEffect(inAppUpdateManager, installMessage, installAction) {
                        inAppUpdateManager.installReady.collect {
                            val result = updateSnackbarHostState.showSnackbar(
                                message = installMessage,
                                actionLabel = installAction,
                                duration = SnackbarDuration.Indefinite,
                            )
                            if (result == SnackbarResult.ActionPerformed) {
                                inAppUpdateManager.completeUpdate()
                            }
                        }
                    }
                    SnackbarHost(
                        hostState = updateSnackbarHostState,
                        modifier = Modifier.align(Alignment.BottomCenter),
                    )
                }
                } // Surface
            }
        }
    }

    override fun onResume() {
        super.onResume()
        // Catch an update that finished downloading while the app was backgrounded.
        if (!BuildConfig.DEBUG) inAppUpdateManager.checkForPendingInstall()
    }

    override fun onDestroy() {
        inAppUpdateManager.unregisterListener()
        super.onDestroy()
    }
}
