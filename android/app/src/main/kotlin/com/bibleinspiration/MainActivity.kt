package com.bibleinspiration

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

            val layoutDirection = LocaleHelper.layoutDirectionFor(uiState.currentLocale)

            val darkTheme = when (uiState.themeMode) {
                "dark" -> true
                "light" -> false
                else -> isSystemInDarkTheme()
            }

            // Build a locale-aware Context so all stringResource() calls inside the
            // composition tree resolve strings from the correct locale's strings.xml
            // without requiring an Activity restart.
            val context = LocalContext.current
            val localizedContext = remember(languageCode) {
                val locale = Locale(languageCode)
                val config = Configuration(context.resources.configuration)
                config.setLocale(locale)
                context.createConfigurationContext(config)
            }

            BibleInspirationTheme(darkTheme = darkTheme) {
                CompositionLocalProvider(
                    LocalLayoutDirection provides layoutDirection,
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
