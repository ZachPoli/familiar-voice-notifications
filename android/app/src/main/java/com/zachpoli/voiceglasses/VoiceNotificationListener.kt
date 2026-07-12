package com.zachpoli.voiceglasses

import android.app.Notification
import android.media.MediaPlayer
import android.os.Handler
import android.os.Looper
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

class VoiceNotificationListener : NotificationListenerService() {

    companion object {
        private const val TAG = "VoiceGlassesNotification"
        private const val API_KEY_HEADER = "X-Voice-Glasses-Key"
        private const val PLACEHOLDER_SERVER_URL =
            "https://example.com/notification"
    }

    /*
     * For the current MVP, only Google Messages notifications
     * are allowed through the listener.
     *
     * More apps can be added later through user controls.
     */
    private val allowedPackages =
        setOf(
            "com.google.android.apps.messaging"
        )

    private val mainHandler =
        Handler(Looper.getMainLooper())

    private var mediaPlayer: MediaPlayer? = null

    override fun onListenerConnected() {
        super.onListenerConnected()

        Log.d(
            TAG,
            "Voice Glasses notification listener connected."
        )
    }

    override fun onNotificationPosted(
        sbn: StatusBarNotification
    ) {
        super.onNotificationPosted(sbn)

        /*
         * Read the master Voice Glasses switch.
         *
         * The preference is shared with MainActivity.
         */
        val preferences =
            getSharedPreferences(
                VOICE_GLASSES_PREFS,
                MODE_PRIVATE
            )

        val voiceGlassesEnabled =
            preferences.getBoolean(
                KEY_VOICE_GLASSES_ENABLED,
                true
            )

        if (!voiceGlassesEnabled) {
            Log.d(
                TAG,
                "Notification skipped because Voice Glasses is paused."
            )

            return
        }

        val packageName = sbn.packageName

        /*
         * Ignore notifications from apps that are not currently
         * approved for the MVP.
         */
        if (packageName !in allowedPackages) {
            Log.d(
                TAG,
                "Notification skipped from package: $packageName"
            )

            return
        }

        val extras = sbn.notification.extras

        val sender =
            extras
                .getCharSequence(Notification.EXTRA_TITLE)
                ?.toString()
                ?.trim()
                .orEmpty()

        val message =
            extras
                .getCharSequence(Notification.EXTRA_TEXT)
                ?.toString()
                ?.trim()
                .orEmpty()

        /*
         * Google Messages can create background service
         * notifications such as:
         *
         * "Messages is doing work in the background"
         *
         * These notifications do not have a real sender.
         *
         * For the MVP, reject any notification that does not
         * contain both a sender and message.
         */
        if (sender.isBlank()) {
            Log.d(
                TAG,
                "Notification skipped because sender is blank. Message: $message"
            )

            return
        }

        if (message.isBlank()) {
            Log.d(
                TAG,
                "Notification skipped because message is blank. Sender: $sender"
            )

            return
        }

        Log.d(
            TAG,
            """
            Notification detected:
            Package: $packageName
            Sender: $sender
            Message: $message
            """.trimIndent()
        )

        /*
         * Network work cannot run on Android's main UI thread,
         * so the request is sent from a background thread.
         */
        Thread {
            sendNotificationToServer(
                sender = sender,
                packageName = packageName,
                message = message
            )
        }.start()
    }

    private fun sendNotificationToServer(
        sender: String,
        packageName: String,
        message: String
    ) {
        var connection: HttpURLConnection? = null

        try {
            val serverUrl =
                BuildConfig.VOICE_GLASSES_SERVER_URL.trim()

            if (
                serverUrl.isBlank() ||
                serverUrl == PLACEHOLDER_SERVER_URL
            ) {
                Log.e(
                    TAG,
                    "Voice Glasses server URL is not configured."
                )

                return
            }

            if (BuildConfig.VOICE_GLASSES_API_KEY.isBlank()) {
                Log.w(
                    TAG,
                    "Voice Glasses API key is not configured. Hosted requests may be rejected."
                )
            }

            val url = URL(serverUrl)

            connection =
                url.openConnection() as HttpURLConnection

            connection.requestMethod = "POST"
            connection.connectTimeout = 10_000
            connection.readTimeout = 60_000
            connection.doOutput = true

            connection.setRequestProperty(
                "Content-Type",
                "application/json"
            )

            if (BuildConfig.VOICE_GLASSES_API_KEY.isNotBlank()) {
                connection.setRequestProperty(
                    API_KEY_HEADER,
                    BuildConfig.VOICE_GLASSES_API_KEY
                )
            }

            val jsonBody =
                JSONObject().apply {
                    put("sender", sender)
                    put("app", packageName)
                    put("message", message)
                }

            connection.outputStream.use { outputStream ->
                outputStream.write(
                    jsonBody
                        .toString()
                        .toByteArray(Charsets.UTF_8)
                )
            }

            val responseCode =
                connection.responseCode

            Log.d(
                TAG,
                "Server response code: $responseCode"
            )

            if (responseCode in 200..299) {
                val audioBytes =
                    connection.inputStream.use { inputStream ->
                        inputStream.readBytes()
                    }

                Log.d(
                    TAG,
                    "Received audio response: ${audioBytes.size} bytes"
                )

                mainHandler.post {
                    playAudio(audioBytes)
                }
            } else {
                val errorMessage =
                    connection.errorStream
                        ?.bufferedReader()
                        ?.use { reader ->
                            reader.readText()
                        }
                        .orEmpty()

                Log.e(
                    TAG,
                    "Server error $responseCode: $errorMessage"
                )
            }
        } catch (exception: Exception) {
            Log.e(
                TAG,
                "Failed to process notification.",
                exception
            )
        } finally {
            connection?.disconnect()
        }
    }

    private fun playAudio(
        audioBytes: ByteArray
    ) {
        try {
            /*
             * Save the returned MP3 bytes temporarily because
             * MediaPlayer can play directly from a file path.
             */
            val audioFile =
                File.createTempFile(
                    "voice_glasses_",
                    ".mp3",
                    cacheDir
                )

            audioFile.writeBytes(audioBytes)

            /*
             * Release any previous MediaPlayer before creating
             * a new one.
             *
             * We will test rapid-message queue behavior separately.
             */
            mediaPlayer?.release()

            mediaPlayer =
                MediaPlayer().apply {
                    setDataSource(audioFile.absolutePath)

                    setOnPreparedListener { player ->
                        Log.d(
                            TAG,
                            "Playing audio response."
                        )

                        player.start()
                    }

                    setOnCompletionListener { player ->
                        Log.d(
                            TAG,
                            "Audio playback finished."
                        )

                        player.release()

                        if (mediaPlayer === player) {
                            mediaPlayer = null
                        }

                        audioFile.delete()
                    }

                    setOnErrorListener { player, what, extra ->
                        Log.e(
                            TAG,
                            "MediaPlayer error. what=$what extra=$extra"
                        )

                        player.release()

                        if (mediaPlayer === player) {
                            mediaPlayer = null
                        }

                        audioFile.delete()

                        true
                    }

                    prepareAsync()
                }
        } catch (exception: Exception) {
            Log.e(
                TAG,
                "Failed to play audio response.",
                exception
            )
        }
    }

    override fun onDestroy() {
        mediaPlayer?.release()
        mediaPlayer = null

        super.onDestroy()
    }
}
