import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

// The app's build number: how many commits changed its sources, counted the
// way ccc counts it (ccc.updates.android_build) — so a pull that changes the
// app makes the installed build older than ccc's, and the app says so.
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
        versionName = "0.1.0"
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
        }
        release {
            isMinifyEnabled = false
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

    testImplementation(libs.junit)
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.test.junit)
    testImplementation(libs.compose.ui.test.junit4)
    debugImplementation(libs.compose.ui.test.manifest)
}
