package com.bibleinspiration

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.bibleinspiration.presentation.screens.ChatScreen
import com.bibleinspiration.presentation.screens.ConversationsScreen
import com.bibleinspiration.presentation.theme.BibleInspirationTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            BibleInspirationTheme {
                val navController = rememberNavController()
                NavHost(
                    navController = navController,
                    startDestination = "conversations",
                ) {
                    composable("conversations") {
                        ConversationsScreen(
                            onNewConversation = { navController.navigate("chat/new") },
                            onSelectConversation = { id -> navController.navigate("chat/$id") },
                        )
                    }
                    composable("chat/{conversationId}") { backStackEntry ->
                        val conversationId = backStackEntry.arguments?.getString("conversationId")
                        ChatScreen(conversationId = conversationId)
                    }
                }
            }
        }
    }
}
