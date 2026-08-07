// gw-chat launches the Garbleworks red-team chat on the pi TUI.
// Replaces gw-chat.ps1: find pi, set env, exec pi -e pi-garbleworks --no-builtin-tools.
package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

func main() {
	root, err := resolveRoot()
	if err != nil {
		fatalf("could not resolve install root: %v", err)
	}
	if err := os.Chdir(root); err != nil {
		fatalf("chdir %s: %v", root, err)
	}

	piCmd, err := findPi()
	if err != nil {
		fmt.Fprintln(os.Stderr, "pi not found on PATH.")
		fmt.Fprintln(os.Stderr, "Install: npm i -g --ignore-scripts @earendil-works/pi-coding-agent")
		os.Exit(1)
	}

	pkg := filepath.Join(root, "pi-garbleworks")
	if st, err := os.Stat(pkg); err != nil || !st.IsDir() {
		fatalf("missing pi-garbleworks at %s", pkg)
	}

	if os.Getenv("GARBLEWORKS_PYTHON") == "" {
		if _, err := exec.LookPath("py"); err == nil {
			_ = os.Setenv("GARBLEWORKS_PYTHON", "py")
		}
	}
	_ = os.Setenv("PYTHONIOENCODING", "utf-8")

	args := append([]string{"-e", pkg, "--no-builtin-tools"}, os.Args[1:]...)

	fmt.Println("Garbleworks · pi red-team chat")
	fmt.Printf("  package: %s\n", pkg)
	fmt.Printf("  pi: %s\n", piCmd)
	fmt.Println("  /gw for status · talk normally · tools fire for real")
	fmt.Println()

	code := run(piCmd, args)
	os.Exit(code)
}

// resolveRoot is the directory that holds pi-garbleworks (repo root).
// Prefer executable location so gw-chat.exe works from PATH or another cwd.
func resolveRoot() (string, error) {
	exe, err := os.Executable()
	if err != nil {
		return "", err
	}
	exe, err = filepath.EvalSymlinks(exe)
	if err != nil {
		// still usable without symlink resolve
		exe, _ = os.Executable()
	}
	dir := filepath.Dir(exe)
	if hasPackage(dir) {
		return dir, nil
	}
	// go run / nested build: walk up a few levels
	for i := 0; i < 4; i++ {
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
		if hasPackage(dir) {
			return dir, nil
		}
	}
	cwd, err := os.Getwd()
	if err != nil {
		return "", err
	}
	if hasPackage(cwd) {
		return cwd, nil
	}
	return "", fmt.Errorf("pi-garbleworks not found near %s or cwd", exe)
}

func hasPackage(dir string) bool {
	st, err := os.Stat(filepath.Join(dir, "pi-garbleworks"))
	return err == nil && st.IsDir()
}

// findPi prefers pi.cmd (npm shim) so Windows does not hit PowerShell policy on pi.ps1.
func findPi() (string, error) {
	if appdata := os.Getenv("APPDATA"); appdata != "" {
		npmPi := filepath.Join(appdata, "npm", "pi.cmd")
		if fileExists(npmPi) {
			return npmPi, nil
		}
	}
	if p, err := exec.LookPath("pi.cmd"); err == nil {
		return p, nil
	}
	if p, err := exec.LookPath("pi"); err == nil {
		return p, nil
	}
	return "", fmt.Errorf("pi not found")
}

func fileExists(path string) bool {
	st, err := os.Stat(path)
	return err == nil && !st.IsDir()
}

func run(name string, args []string) int {
	cmd := exec.Command(name, args...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = os.Environ()

	// On Windows, .cmd needs cmd.exe /c so CreateProcess does not choke.
	if runtime.GOOS == "windows" && isBatch(name) {
		full := append([]string{"/c", name}, args...)
		cmd = exec.Command("cmd.exe", full...)
		cmd.Stdin = os.Stdin
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		cmd.Env = os.Environ()
	}

	err := cmd.Run()
	if err == nil {
		return 0
	}
	if ee, ok := err.(*exec.ExitError); ok {
		return ee.ExitCode()
	}
	fmt.Fprintf(os.Stderr, "failed to start %s: %v\n", name, err)
	return 1
}

func isBatch(path string) bool {
	ext := strings.ToLower(filepath.Ext(path))
	return ext == ".cmd" || ext == ".bat"
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(1)
}
