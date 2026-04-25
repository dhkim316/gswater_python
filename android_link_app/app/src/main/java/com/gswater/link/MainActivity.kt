package com.gswater.link

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        openDashboard()
    }

    private fun openDashboard() {
        val uri = Uri.parse(DASHBOARD_URL)
        val chromeIntent = Intent(Intent.ACTION_VIEW, uri).apply {
            setPackage(CHROME_PACKAGE)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        val fallbackIntent = Intent(Intent.ACTION_VIEW, uri).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        try {
            startActivity(chromeIntent)
        } catch (_: ActivityNotFoundException) {
            try {
                startActivity(fallbackIntent)
            } catch (_: Exception) {
                Toast.makeText(this, getString(R.string.browser_not_found), Toast.LENGTH_LONG).show()
            }
        } finally {
            finish()
        }
    }

    companion object {
        private const val CHROME_PACKAGE = "com.android.chrome"
        private const val DASHBOARD_URL = "http://222.103.74.152:1880/ui/#!/5"
    }
}
