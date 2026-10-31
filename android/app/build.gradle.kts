import java.util.Properties
import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

// The app's build number: how many commits changed its sources — it only
// grows, which Android needs to install a newer app over an older one. The
// version people see (versionName) is the release's: CI passes it from the
// tag (-Pccc.version=1.2.3); a build made by hand is "0.0.0-dev" and never
// asks to be updated.
val appBuild: Int = runCatching {
    providers.exec {
        commandLine("git", "rev-list", "--count", "HEAD", "--", "src/main")
        workingDir = projectDir
    }.standardOutput.asText.get().trim().toInt()
}.getOrDefault(0).coerceAtLeast(1)

android {
    namespace = "io.github.luquas95.ccc"
    compileSdk = 36

    defaultConfig {
        applicationId = "io.github.luquas95.ccc"
        minSdk = 29
        targetSdk = 36
        versionCode = appBuild
        versionName = (findProperty("ccc.version") as String?)?.removePrefix("v") ?: "0.0.0-dev"
    }

    // The release key: from CI's environment (ANDROID_KEYSTORE_FILE …) or, on this
    // computer, from ~/.android/ccc-release.properties. Without either, the release
    // build isn't signed with it (Gradle then leaves it unsigned).
    val releaseKey = Properties().apply {
        val file = File(System.getProperty("user.home"), ".android/ccc-release.properties")
        if (file.exists()) file.inputStream().use { load(it) }
    }
    val keystorePath = System.getenv("ANDROID_KEYSTORE_FILE") ?: releaseKey.getProperty("storeFile")
    signingConfigs {
        if (keystorePath != null) {
            create("release") {
                storeFile = File(keystorePath)
                storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD") ?: releaseKey.getProperty("storePassword")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS") ?: releaseKey.getProperty("keyAlias", "ccc")
                keyPassword = System.getenv("ANDROID_KEYSTORE_PASSWORD") ?: releaseKey.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
        }
        release {
            isMinifyEnabled = false
            signingConfigs.findByName("release")?.let { signingConfig = it }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
    }

    testOptions {
        unitTests.isIncludeAndroidResources = true
        // ScreenshotsTest: capture the window as Robolectric draws it.
        unitTests.all { it.systemProperty("robolectric.pixelCopyRenderMode", "hardware") }
    }

    androidResources {
        @Suppress("UnstableApiUsage")
        generateLocaleConfig = true
    }
}

tasks.withType<KotlinCompile>().configureEach {
    compilerOptions.jvmTarget.set(JvmTarget.JVM_17)
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.compose.ui)
    implementation(libs.compose.foundation)
    implementation(libs.compose.material3)
    implementation(libs.compose.material.icons)
    implementation(libs.compose.ui.tooling.preview)
    debugImplementation(libs.compose.ui.tooling)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.okhttp)
    implementation(libs.zxing.embedded)

    testImplementation(libs.junit)
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.test.junit)
    testImplementation(libs.compose.ui.test.junit4)
    debugImplementation(libs.compose.ui.test.manifest)
}
