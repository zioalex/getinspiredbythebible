package com.bibleinspiration

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.platform.LocalLayoutDirection
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

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val chatViewModel: ChatViewModel = hiltViewModel()
            val uiState by chatViewModel.uiState.collectAsState()
            val layoutDirection = LocaleHelper.layoutDirectionFor(uiState.currentLocale)

            val darkTheme = when (uiState.themeMode) {
                "dark" -> true
                "light" -> false
                else -> isSystemInDarkTheme()
            }

            BibleInspirationTheme(darkTheme = darkTheme) {
                CompositionLocalProvider(LocalLayoutDirection provides layoutDirection) {
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
                            ChatScreen(conversationId = conversationId)
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
