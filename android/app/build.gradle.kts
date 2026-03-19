plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.example.myapplication"
    compileSdk = 36

    buildFeatures {
        buildConfig = true
    }

    defaultConfig {
        applicationId = "com.example.myapplication"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // Coach backend — debug default routes to Android emulator host.
        // Override COACH_API_BASE / COACH_API_KEY env vars for release builds.
        buildConfigField("String", "COACH_API_BASE", "\"http://10.0.2.2:8000\"")
        buildConfigField("String", "COACH_API_KEY", "\"dev-key\"")

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    // 🛡️ FIX: Ensure Android system calls (like Log) don't crash JVM unit tests
    testOptions {
        unitTests.isReturnDefaultValues = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            // Production values injected via env vars at build time.
            // Falls back to dev defaults so CI never fails on a missing secret.
            val prodApiBase: String = System.getenv("COACH_API_BASE") ?: "http://10.0.2.2:8000"
            val prodApiKey: String = System.getenv("COACH_API_KEY") ?: "dev-key"
            buildConfigField("String", "COACH_API_BASE", "\"$prodApiBase\"")
            buildConfigField("String", "COACH_API_KEY", "\"$prodApiKey\"")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.appcompat:appcompat:1.7.1")
    implementation("com.google.android.material:material:1.13.0")

    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.activity:activity-ktx:1.12.2")
    implementation("androidx.security:security-crypto:1.1.0-alpha06")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.7.3")
    androidTestImplementation("androidx.test.ext:junit:1.3.0")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.7.0")
}
