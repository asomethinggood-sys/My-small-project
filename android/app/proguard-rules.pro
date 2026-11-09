# Gomobile and Rust JNI entry points must retain their Java names.
-keep class go.** { *; }
-keep class libv2ray.** { *; }
-keep class app.continuum.RustCore { *; }
-keep class * implements libv2ray.CoreCallbackHandler { *; }
-keepclasseswithmembernames,includedescriptorclasses class * { native <methods>; }
