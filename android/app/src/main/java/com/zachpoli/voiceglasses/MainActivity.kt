package com.zachpoli.voiceglasses

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.zachpoli.voiceglasses.ui.theme.VoiceGlassesTheme


const val VOICE_GLASSES_PREFS =
    "voice_glasses_preferences"


const val KEY_VOICE_GLASSES_ENABLED =
    "voice_glasses_enabled"


class MainActivity : ComponentActivity() {

    override fun onCreate(
        savedInstanceState: Bundle?
    ) {
        super.onCreate(savedInstanceState)


        val preferences =
            getSharedPreferences(
                VOICE_GLASSES_PREFS,
                MODE_PRIVATE
            )


        setContent {

            VoiceGlassesTheme {

                var voiceGlassesEnabled by remember {

                    mutableStateOf(
                        preferences.getBoolean(
                            KEY_VOICE_GLASSES_ENABLED,
                            true
                        )
                    )
                }


                Scaffold(
                    modifier = Modifier.fillMaxSize()
                ) { innerPadding ->

                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(innerPadding)
                            .padding(32.dp),

                        horizontalAlignment =
                        Alignment.CenterHorizontally,

                        verticalArrangement =
                        Arrangement.Center
                    ) {

                        Text(
                            text = "Voice Glasses",
                            style =
                            MaterialTheme.typography.headlineLarge
                        )


                        Spacer(
                            modifier = Modifier.height(16.dp)
                        )


                        Text(
                            text =
                            if (voiceGlassesEnabled) {
                                "Notification speech is enabled"
                            } else {
                                "Notification speech is paused"
                            },

                            style =
                            MaterialTheme.typography.bodyLarge
                        )


                        Spacer(
                            modifier = Modifier.height(24.dp)
                        )


                        Switch(
                            checked = voiceGlassesEnabled,

                            onCheckedChange = { enabled ->

                                voiceGlassesEnabled =
                                    enabled


                                preferences
                                    .edit()
                                    .putBoolean(
                                        KEY_VOICE_GLASSES_ENABLED,
                                        enabled
                                    )
                                    .apply()
                            }
                        )


                        Spacer(
                            modifier = Modifier.height(24.dp)
                        )


                        Text(
                            text =
                            "Turn Voice Glasses on to hear notifications spoken aloud through your connected audio device.",

                            style =
                            MaterialTheme.typography.bodyMedium
                        )
                    }
                }
            }
        }
    }
}