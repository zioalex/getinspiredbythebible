package com.bibleinspiration

import android.content.Context
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
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.bibleinspiration.presentation.screens.ChatScreen
import com.bibleinspiration.presentation.screens.ConversationsScreen
import com.bibleinspiration.presentation.screens.SettingsScreen
import com.bibleinspiration.presentation.theme.BibleInspirationTheme
import com.bibleinspiration.presentation.viewmodels.ChatViewModel
import com.bibleinspiration.utils.LocaleHelper
import dagger.hilt.android.AndroidEntryPoint
import java.util.Locale

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
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
            // To keep hiltViewModel() working (it needs an Activity context), we only wrap
            // LocalContext at the NavHost level — Hilt resolves ViewModels before reaching it.
            val activityContext = LocalContext.current
            val localizedConfiguration = remember(languageCode) {
                val locale = Locale(languageCode)
                Configuration(activityContext.resources.configuration).also { cfg ->
                    cfg.setLocale(locale)
                }
            }
            // createConfigurationContext returns a ContextWrapper whose Resources use the
            // overridden locale, so stringResource() picks up translated strings in real time.
            val localizedContext: Context = remember(languageCode) {
                activityContext.createConfigurationContext(localizedConfiguration)
            }

            BibleInspirationTheme(darkTheme = darkTheme) {
                CompositionLocalProvider(
                    LocalLayoutDirection provides layoutDirection,
                    LocalConfiguration provides localizedConfiguration,
                    LocalContext provides localizedContext,
                ) {
                    val navController = rememberNavController()
                    NavHost(
                        navController = navController,
                        startDestination = "conversations",
                    ) {
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
