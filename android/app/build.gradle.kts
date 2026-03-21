plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Release signing — populated from environment variables injected by CI.
// When any variable is absent (local dev, unit-test CI) the signingConfig is
// skipped and Gradle produces app-release-unsigned.apk as before.
val releaseKeystoreFile: String? = System.getenv("KEYSTORE_FILE")
val releaseKeyAlias: String? = System.getenv("KEY_ALIAS")
val releaseKeyPassword: String? = System.getenv("KEY_PASSWORD")
val releaseStorePassword: String? = System.getenv("STORE_PASSWORD")
val hasReleaseSigningConfig: Boolean = listOf(
    releaseKeystoreFile, releaseKeyAlias, releaseKeyPassword, releaseStorePassword,
).all { it != null }

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

    testOptions {
        unitTests {
            isReturnDefaultValues = true
            // Force IPv4 so HttpURLConnection and MockWebServer use the same
            // loopback address on all platforms (avoids Windows IPv6/keep-alive races).
            all { it.jvmArgs("-Djava.net.preferIPv4Stack=true") }
        }
    }

    if (hasReleaseSigningConfig) {
        signingConfigs {
            create("release") {
                storeFile = file(releaseKeystoreFile!!)
                keyAlias = releaseKeyAlias!!
                keyPassword = releaseKeyPassword!!
                storePassword = releaseStorePassword!!
            }
        }
    }

    buildTypes {
        release {
            if (hasReleaseSigningConfig) {
                signingConfig = signingConfigs.getByName("release")
            }
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            // COACH_API_BASE is a plain configuration value (not a secret) — it is
            // visible in the decompiled APK regardless of obfuscation. Pass it as a
            // GitHub Actions variable (vars.COACH_API_BASE), not a secret.
            // COACH_API_KEY ends up in the APK binary and is therefore semi-public;
            // treat it as a rate-limit shield only, not real authentication. Real
            // per-user auth uses JWT tokens issued by /auth/login. Pass it as a
            // GitHub Actions secret (secrets.COACH_API_KEY).
            //
            // Falls back to dev defaults when env vars are absent (e.g. unit-test CI).
            val prodApiBase: String = System.getenv("COACH_API_BASE") ?: "http://10.0.2.2:8000"
            val prodApiKey: String = System.getenv("COACH_API_KEY") ?: "dev-key"
            // Hard-fail if COACH_API_BASE is explicitly provided but uses plain HTTP.
            if (System.getenv("COACH_API_BASE") != null && !prodApiBase.startsWith("https://")) {
                error(
                    "Release build requires COACH_API_BASE to start with https://. " +
                    "Got: $prodApiBase — set a valid TLS endpoint."
                )
            }
            buildConfigField("String", "COACH_API_BASE", "\"$prodApiBase\"")
            buildConfigField("String", "COACH_API_KEY", "\"$prodApiKey\"")
        }
        debug {
            // Allow developers to point at a remote server (e.g. Hetzner) without
            // modifying source code — export COACH_API_BASE / COACH_API_KEY in the
            // shell, then re-sync Gradle (Step 3.4).
            val debugApiBase: String = System.getenv("COACH_API_BASE") ?: "http://10.0.2.2:8000"
            val debugApiKey: String = System.getenv("COACH_API_KEY") ?: "dev-key"
            buildConfigField("String", "COACH_API_BASE", "\"$debugApiBase\"")
            buildConfigField("String", "COACH_API_KEY", "\"$debugApiKey\"")
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
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
    // Real org.json implementation — overrides the Android stub (android.jar) so that
    // production clients that use JSONObject can be exercised in host JVM unit tests.
    testImplementation("org.json:json:20231013")
    androidTestImplementation("androidx.test.ext:junit:1.3.0")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.7.0")
}
