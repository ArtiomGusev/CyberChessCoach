plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.example.myapplication"
    compileSdk = 35 // ✅ Updated to 35 to support latest AARs

    defaultConfig {
        applicationId = "com.example.myapplication"
        minSdk = 26
        targetSdk = 35 // ✅ Updated to 35
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        ndk {
            // ✅ Correct Kotlin Script syntax
            abiFilters += "arm64-v8a"
        }
    }

    // ✅ Added External Native Build configuration
    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
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
    implementation("androidx.core:core-ktx:1.15.0") // ✅ Updated to latest
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")

    // Lifecycle & ViewModel
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.8.7") // ✅ Using more common stable version
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    
    // Activity KTX
    implementation("androidx.activity:activity-ktx:1.9.3") // ✅ Using stable 1.9.x

    // Unit Testing
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
}
