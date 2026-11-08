import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

val localPortalHost = providers.gradleProperty("sevamritaLocalHost").orElse("10.0.2.2").get()
val localPortalOnly = providers.gradleProperty("sevamritaLocalOnly").orElse("false").get().toBooleanStrict()
val localOctets = localPortalHost.split('.').map { it.toIntOrNull() }
require(localOctets.size == 4 && localOctets.all { it != null && it in 0..255 } &&
    (localOctets[0] == 10 || (localOctets[0] == 172 && localOctets[1] in 16..31) ||
        (localOctets[0] == 192 && localOctets[1] == 168))) {
    "sevamritaLocalHost must be a private Wi-Fi IPv4 address."
}

val releaseKey = rootProject.file("release-keystore.properties")
val releaseSigning = Properties().apply { if (releaseKey.exists()) releaseKey.inputStream().use { load(it) } }

android {
    namespace = "org.sevamrita.mobile"
    compileSdk = 35

    defaultConfig {
        applicationId = "org.sevamrita.mobile"
        minSdk = 26
        targetSdk = 35
        versionCode = 23
        versionName = "0.6.0"
        manifestPlaceholders["appLabel"] = "SF Tasks"
        buildConfigField("String", "APP_NAME", "\"SF Tasks\"")
        buildConfigField("String", "DEFAULT_LOCAL_HOST", "\"\"")
        buildConfigField("boolean", "LOCAL_PORTAL_ONLY", "false")
        testInstrumentationRunner = "org.sevamrita.mobile.FeatureAcceptanceInstrumentation"
    }

    signingConfigs {
        if (releaseKey.exists()) create("sfTasks") {
            storeFile = rootProject.file(releaseSigning.getProperty("storeFile"))
            storePassword = releaseSigning.getProperty("storePassword")
            keyAlias = releaseSigning.getProperty("keyAlias")
            keyPassword = releaseSigning.getProperty("keyPassword")
        }
    }

    buildTypes {
        debug {
            manifestPlaceholders["cleartextAllowed"] = "true"
            buildConfigField("String", "DEFAULT_LOCAL_HOST", "\"$localPortalHost\"")
            buildConfigField("boolean", "LOCAL_PORTAL_ONLY", localPortalOnly.toString())
            if (localPortalOnly) {
                applicationIdSuffix = ".local"
                versionNameSuffix = "-local"
                manifestPlaceholders["appLabel"] = "SF testing"
                buildConfigField("String", "APP_NAME", "\"SF testing\"")
            }
        }
        release {
            if (releaseKey.exists()) signingConfig = signingConfigs.getByName("sfTasks")
            isMinifyEnabled = true
            manifestPlaceholders["cleartextAllowed"] = "false"
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true; buildConfig = true }
    testOptions.unitTests.all { it.systemProperty("sevamrita.manifest", project.file("src/main/AndroidManifest.xml").absolutePath) }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2025.05.01"))
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.google.firebase:firebase-messaging:24.1.2")

    testImplementation("junit:junit:4.13.2")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
