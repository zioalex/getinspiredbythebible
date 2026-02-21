package com.getinspiredbythebible

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.getinspiredbythebible.ui.chat.ChatScreen
import com.getinspiredbythebible.ui.theme.GetInspiredByTheBibleTheme
import dagger.hilt.android.AndroidEntryPoint

/**
 * Single-Activity entry point for the app.
 *
 * [@AndroidEntryPoint] enables Hilt injection for this activity and any
 * Fragment / Composable ViewModels created within it.
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            GetInspiredByTheBibleTheme {
                ChatScreen()
            }
        }
    }
}
