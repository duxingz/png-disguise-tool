import org.jetbrains.compose.desktop.application.dsl.TargetFormat

plugins {
    kotlin("jvm")
    id("org.jetbrains.compose")
    id("org.jetbrains.kotlin.plugin.compose")
}

kotlin {
    jvmToolchain(21)
}

dependencies {
    implementation(project(":core"))
    implementation(compose.desktop.currentOs)
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.9.0")
    // GIF 解码与 JVM 图片 IO(jvmimpl 包)
    implementation("com.madgag:animated-gif-lib:1.4")
    testImplementation(kotlin("test"))
    testImplementation("com.madgag:animated-gif-lib:1.4")
}

compose.desktop {
    application {
        mainClass = "com.pngdisguise.desktop.MainKt"
        nativeDistributions {
            targetFormats(TargetFormat.Msi)
            packageName = "png伪装工具"
            packageVersion = "1.0.0"
            // exe/安装器图标(用户提供的封面图转制)
            linux {
                iconFile.set(file("src/main/resources/launcher_icon.ico"))
            }
            windows {
                iconFile.set(file("src/main/resources/launcher_icon.ico"))
                menu = true
                shortcut = true
                dirChooser = true
            }
        }
    }
}
