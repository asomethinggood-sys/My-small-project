using System;
using System.IO;
using System.Security.Cryptography;
using System.Text.Json;

namespace Continuum;

public sealed record Settings(string Source, bool Imported, int Mtu)
{
    public const string DefaultSource = "https://github.com/asomethinggood-sys/My-small-project/releases/download/vpn-config/config.txt";
    static string DirectoryPath => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Continuum");
    static string FilePath => Path.Combine(DirectoryPath, "settings.dat");
    public static Settings Load()
    {
        try
        {
            var bytes = ProtectedData.Unprotect(File.ReadAllBytes(FilePath), null, DataProtectionScope.CurrentUser);
            return JsonSerializer.Deserialize<Settings>(bytes) ?? new(DefaultSource, false, 1400);
        }
        catch { return new(DefaultSource, false, 1400); }
    }
    public void Save()
    {
        Directory.CreateDirectory(DirectoryPath);
        var bytes = ProtectedData.Protect(JsonSerializer.SerializeToUtf8Bytes(this), null, DataProtectionScope.CurrentUser);
        File.WriteAllBytes(FilePath + ".tmp", bytes);
        File.Move(FilePath + ".tmp", FilePath, true);
    }
}
