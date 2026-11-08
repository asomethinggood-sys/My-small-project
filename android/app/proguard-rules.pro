# Gomobile calls these Java interfaces/classes by JNI names. Do not rename or remove them.
-keep class go.** { *; }
-keep class libv2ray.** { *; }
-keep class * implements libv2ray.CoreCallbackHandler { *; }
-keepclasseswithmembernames,includedescriptorclasses class * { native <methods>; }
