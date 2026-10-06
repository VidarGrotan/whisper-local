// Starts the repository-local Whisper executable with its bundled NVIDIA DLLs.
// Built as a windowless app so Start-menu and taskbar launches stay unobtrusive.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

[assembly: AssemblyTitle("Whisper Local")]
[assembly: AssemblyDescription("Starts the configured local Whisper dictation app")]
[assembly: AssemblyProduct("Whisper Local")]
[assembly: AssemblyVersion("1.0.0.0")]

internal static class WhisperLocalLauncher
{
    private const string DiagnosticsSwitch = "--launcher-diagnostics";

    [STAThread]
    private static int Main(string[] args)
    {
        string project = Path.GetFullPath(AppDomain.CurrentDomain.BaseDirectory)
            .TrimEnd(Path.DirectorySeparatorChar);
        string sitePackages = Path.Combine(project, ".venv", "Lib", "site-packages");
        string target = Path.Combine(project, ".venv", "Scripts", "whisper-local.exe");
        string[] cudaDirectories =
        {
            Path.Combine(sitePackages, "nvidia", "cuda_runtime", "bin"),
            Path.Combine(sitePackages, "nvidia", "cublas", "bin"),
            Path.Combine(sitePackages, "nvidia", "cudnn", "bin"),
        };
        string pathPrefix = string.Join(Path.PathSeparator.ToString(), cudaDirectories);
        string runtimePath = pathPrefix + Path.PathSeparator
            + (Environment.GetEnvironmentVariable("PATH") ?? string.Empty);

        if (args.Length >= 2 && args[0] == DiagnosticsSwitch)
        {
            WriteDiagnostics(args[1], project, target, pathPrefix, args);
            return 0;
        }

        if (!File.Exists(target))
        {
            MessageBox.Show(
                "Whisper Local could not be found at:\n" + target,
                "Whisper Local",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 2;
        }

        try
        {
            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = target,
                Arguments = JoinArguments(args),
                WorkingDirectory = project,
                UseShellExecute = false,
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden,
            };
            startInfo.EnvironmentVariables["PATH"] = runtimePath;
            Process.Start(startInfo);
            return 0;
        }
        catch (Exception exception)
        {
            MessageBox.Show(
                "Whisper Local could not be started.\n\n" + exception.Message,
                "Whisper Local",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 1;
        }
    }

    private static void WriteDiagnostics(
        string outputPath,
        string project,
        string target,
        string pathPrefix,
        string[] args)
    {
        List<string> lines = new List<string>
        {
            "PROJECT=" + project,
            "TARGET=" + target,
            "WORKING_DIRECTORY=" + project,
            "PATH_PREFIX=" + pathPrefix,
        };
        for (int index = 2; index < args.Length; index++)
        {
            lines.Add("ARGUMENT_" + (index - 2) + "=" + args[index]);
        }
        File.WriteAllLines(outputPath, lines.ToArray(), new UTF8Encoding(false));
    }

    private static string JoinArguments(string[] args)
    {
        string[] quoted = new string[args.Length];
        for (int index = 0; index < args.Length; index++)
        {
            quoted[index] = QuoteArgument(args[index]);
        }
        return string.Join(" ", quoted);
    }

    private static string QuoteArgument(string argument)
    {
        if (argument.Length > 0
            && argument.IndexOfAny(new[] { ' ', '\t', '\n', '\v', '"' }) < 0)
        {
            return argument;
        }

        StringBuilder result = new StringBuilder();
        result.Append('"');
        int backslashes = 0;
        foreach (char character in argument)
        {
            if (character == '\\')
            {
                backslashes++;
                continue;
            }
            if (character == '"')
            {
                result.Append('\\', backslashes * 2 + 1);
                result.Append('"');
                backslashes = 0;
                continue;
            }
            result.Append('\\', backslashes);
            backslashes = 0;
            result.Append(character);
        }
        result.Append('\\', backslashes * 2);
        result.Append('"');
        return result.ToString();
    }
}
