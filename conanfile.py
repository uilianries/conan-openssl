from conans import ConanFile, AutoToolsBuildEnvironment
from conans import tools
import os
import sys


class OpenSSLConan(ConanFile):
    name = "OpenSSL"
    version = "1.1.1c"
    description = "OpenSSL is an open source project that provides a robust, commercial-grade, and full-featured " \
                  "toolkit for the Transport Layer Security (TLS) and Secure Sockets Layer (SSL) protocols"
    topics = ("conan", "openssl", "tls", "encryption")
    url = "http://github.com/conan-community/conan-openssl"
    homepage = "https://www.openssl.org"
    author = "Conan Community"
    license = "The current OpenSSL licence is an 'Apache style' license: https://www.openssl.org/source/license.html"
    settings = "os", "compiler", "arch", "build_type"
    # https://github.com/openssl/openssl/blob/OpenSSL_1_1_1c/INSTALL
    options = {"no_threads": [True, False],
               "no_zlib": [True, False],
               "shared": [True, False],
               "no_asm": [True, False],
               "386": [True, False],
               "no_sse2": [True, False],
               "no_bf": [True, False],
               "no_cast": [True, False],
               "no_des": [True, False],
               "no_dh": [True, False],
               "no_dsa": [True, False],
               "no_hmac": [True, False],
               "no_md2": [True, False],
               "no_md5": [True, False],
               "no_mdc2": [True, False],
               "no_rc2": [True, False],
               "no_rc4": [True, False],
               "no_rc5": [True, False],
               "no_rsa": [True, False],
               "no_sha": [True, False],
               "no_fpic": [True, False],
               "no_async": [True, False],
               "no_dso": [True, False],
               "capieng_dialog": [True, False]}
    default_options = "=False\n".join(options.keys()) + "=False"

    # When a new version is available they move the tar.gz to old/ location
    source_tgz = "https://www.openssl.org/source/openssl-%s.tar.gz" % version
    source_tgz_old = "https://www.openssl.org/source/old/1.1.1/openssl-%s.tar.gz" % version

    def build_requirements(self):
        # useful for example for conditional build_requires
        if self.compiler == "Visual Studio":
            self.build_requires("strawberryperl/5.26.0@conan/stable")
            if not self.options.no_asm:
                self.build_requires("nasm/2.13.01@conan/stable")

    def source(self):
        self.output.info("Downloading %s" % self.source_tgz)
        try:
            tools.download(self.source_tgz_old, "openssl.tar.gz")
        except:
            tools.download(self.source_tgz, "openssl.tar.gz")
        tools.unzip("openssl.tar.gz")
        tools.check_sha256("openssl.tar.gz",
                           "f6fb3079ad15076154eda9413fed42877d668e7069d9b87396d0804fdb3f4c90")
        os.unlink("openssl.tar.gz")

    def configure(self):
        del self.settings.compiler.libcxx

    def config_options(self):
        if self.settings.os != "Windows":
            del self.options.capieng_dialog

    def requirements(self):
        if not self.options.no_zlib:
            self.requires("zlib/1.2.11@conan/stable")

    @property
    def subfolder(self):
        return os.path.join(self.source_folder, "openssl-%s" % self.version)

    @property
    def arch(self):
        return self.settings.arch

    @property
    def compiler(self):
        return self.settings.compiler

    def build(self):
        if self.settings.os in ["Linux", "SunOS", "FreeBSD", "Android", "Macos"] or \
                (self.settings.os == "Windows" and self.compiler == "gcc"):
            self.unix_build()
        elif self.settings.os == "iOS":
            self.ios_build()
        elif self.compiler == "Visual Studio":
            self.visual_build()
        elif self.settings.os == "Emscripten":
            self.emscripten_build()
        else:
            raise Exception("Unsupported operating system: %s" % self.settings.os)

    def run_in_src(self, command, show_output=False, win_bash=False):
        if not show_output and not tools.os_info.is_windows and tools.which("bash"):
            command += ' | while read line; do printf "%c" .; done'
            # pipe doesn't fail if first part fails
            command = 'bash -l -c -o pipefail "%s"' % command.replace('"', '\\"')
        with tools.chdir(self.subfolder):
            self.output.write("------RUNNING-------\n%s" % command)
            if self.settings.compiler == "clang" and "TRAVIS" in os.environ:  # Output ruin travis builds
                from six import StringIO
                buf = StringIO()
            else:
                buf = True
            self.run(command, win_bash=win_bash, output=buf)
        self.output.writeln(" ")

    def _get_config_options_string(self):
        config_options_string = ""
        if "zlib" in self.deps_cpp_info.deps:
            zlib_info = self.deps_cpp_info["zlib"]
            include_path = zlib_info.include_paths[0]
            if self.settings.os == "Windows":
                lib_path = "%s/%s.lib" % (zlib_info.lib_paths[0], zlib_info.libs[0])
            else:
                lib_path = zlib_info.lib_paths[0]  # Just path, linux will find the right file
            config_options_string += ' --with-zlib-include="%s"' % include_path
            config_options_string += ' --with-zlib-lib="%s"' % lib_path
            self.output.info("=====> Options: %s" % config_options_string)

        for option_name in self.options.values.fields:
            activated = getattr(self.options, option_name)
            if activated:
                self.output.info("Activated option! %s" % option_name)
                config_options_string += " %s" % option_name.replace("_", "-")

        return config_options_string

    def _get_flags(self):

        if self.settings.os != "Windows":
            env_build = AutoToolsBuildEnvironment(self)
            if self.settings.os == "iOS":
                # in OpenSSL 1.1.1x having the following args "offends" (sic) the Configure script
                env_build.flags.remove("-arch")
                if "armv7" in env_build.flags:
                    env_build.flags.remove("armv7")
                if "armv8" in env_build.flags:
                    env_build.flags.remove("armv8")
                if "arm64" in env_build.flags:
                    env_build.flags.remove("arm64")

            extra_flags = ' '.join(env_build.flags)
            extra_flags += " -fPIC" if not self.options.no_fpic else ""
            if self.settings.build_type == "Debug":
                extra_flags += " -O0"
                if self.compiler in ["apple-clang", "clang", "gcc"]:
                    extra_flags += " -g3 -fno-omit-frame-pointer -fno-inline-functions"
                if self.settings.os in ["Linux", "SunOS", "FreeBSD", "Android"]:
                    extra_flags += " no-asm"
        else:
            extra_flags = "--debug" if self.settings.build_type == "Debug" else "--release"
            if self.options.capieng_dialog:
                extra_flags += " -DOPENSSL_CAPIENG_DIALOG=1"
        extra_flags += " shared" if self.options.shared else " no-shared"
        if self.settings.os == "Android":
            # see NOTES.ANDROID
            extra_flags += " -D__ANDROID_API__=%s" % str(self.settings.os.api_level)
        if self.settings.os == "Emscripten":
            extra_flags += " CROSS_COMPILE= -no-asm -D__STDC_NO_ATOMICS__=1"

        extra_flags += self._get_config_options_string()
        return extra_flags

    def _get_target(self):
        target_prefix = ""

        if self.settings.os == "Windows" and self.settings.compiler == "Visual Studio":
            target = "VC-WIN%s" % ("32" if self.arch == "x86" else "64A")
        elif self.settings.os == "Linux":
            target = {"x86": "linux-x86",
                      "x86_64": "linux-x86_64",
                      "armv6": "linux-armv4",
                      "armv7": "linux-armv4",
                      "armv7hf": "linux-armv4",
                      "armv8": "linux-aarch64",
                      "mips": "linux-mips32",
                      "mips64": "linux-mips64",
                      "ppc64le": "linux-ppc64",
                      "ppc64": "linux-ppc64"}.get(str(self.arch), None)
            if self.arch in ["x86", "x86_64"] and self.compiler == "clang":
                target += "-clang"
            if not target:
                raise Exception("Unsupported arch '%s' for Linux" % self.arch)
        elif self.settings.os == "Macos":
            target = {"x86": "darwin-i386-cc",
                      "x86_64": "darwin64-x86_64-cc"}.get(str(self.arch))
        elif self.settings.os == "Android":
            target = {"armv7": "android-arm",
                      "armv7hf": "android-arm",
                      "armv8": "android-arm64",
                      "x86": "android-x86",
                      "x86_64": "android-x86_64",
                      "mips": "android-mips",
                      "mips64": "android-mips64"}.get(str(self.arch), None)
            if not target:
                raise Exception("Unsupported arch for android")
        elif self.settings.os == "SunOS":
            if self.compiler in ["apple-clang", "clang", "gcc"]:
                suffix = "-gcc"
            elif self.compiler == "sun-cc":
                suffix = "-cc"
            else:
                raise Exception("Unsupported compiler on SunOS: %s" % self.compiler)

            # OpenSSL has no debug profile for non sparcv9 machine
            if self.arch != "sparcv9":
                target_prefix = ""

            if self.arch in ["sparc", "x86"]:
                target = "%ssolaris-%s%s" % (target_prefix, self.arch, suffix)
            elif self.arch in ["sparcv9", "x86_64"]:
                target = "%ssolaris64-%s%s" % (target_prefix, self.arch, suffix)
            else:
                raise Exception("Unsupported arch on SunOS: %s" % self.arch)

        elif self.settings.os == "FreeBSD":
            target = "%sBSD-%s" % (target_prefix, self.arch)
        elif self.settings.os == "Windows" and self.compiler == "gcc":
            target = "mingw" if self.arch == "x86" else "mingw64"
        else:
            raise Exception("Unsupported operating system: %s" % self.settings.os)

        return target

    def _patch_makefile(self):
        if self.settings.os == "Macos":
            self._patch_install_name()

    def emscripten_build(self):
        win_bash = sys.platform == "win32"
        self.run_in_src("emconfigure ./Configure cc %s" % self._get_flags(), show_output=True, win_bash=win_bash)
        self.run_in_src("emmake make", show_output=True, win_bash=win_bash)

    def unix_build(self):
        win_bash = sys.platform == "win32"
        target = self._get_target()

        self.run_in_src("./Configure %s %s" % (target, self._get_flags()), win_bash=win_bash)
        self.run_in_src("make depend")

        self._patch_makefile()

        self.output.warn("----------MAKE OPENSSL %s-------------" % self.version)
        self.run_in_src("make -j%s" % tools.cpu_count(), show_output=True, win_bash=win_bash)

    def ios_build(self):
        config_options_string = self._get_flags()
        command = "./Configure iphoneos-cross %s" % config_options_string

        xcrun = tools.XCRun(self.settings)
        cc = xcrun.find("clang")

        cc += " -arch %s" % tools.to_apple_arch(self.arch)
        if not str(self.arch).startswith("arm"):
            cc += " -DOPENSSL_NO_ASM"

        try:
            cc += " -mios-version-min=%s" % self.settings.os.version
            self.output.info("iOS deployment target: %s" % self.settings.os.version)
        except:
            pass

        cc += " -fembed-bitcode"

        os.environ["CROSS_SDK"] = os.path.basename(xcrun.sdk_path)
        os.environ["CROSS_TOP"] = os.path.dirname(os.path.dirname(xcrun.sdk_path))

        command = 'CC="%s" %s' % (cc, command)

        self.run_in_src(command)
        self._patch_install_name()
        self.output.warn("----------MAKE OPENSSL %s-------------" % self.version)
        self.run_in_src("make -j%s" % tools.cpu_count())

    def _patch_install_name(self):
        old_str = '-install_name $(INSTALLTOP)/$(LIBDIR)/'
        new_str = '-install_name '
        tools.replace_in_file("%s/Makefile" % self.subfolder, old_str, new_str,
                              strict=self.in_local_cache)

    def _patch_runtime(self):
        # Replace runtime in ntdll.mak and nt.mak
        def replace_runtime_in_file(filename):
            replaced = False
            runtimes = ["MDd", "MTd", "MD", "MT"]
            for e in runtimes:
                if e != self.settings.compiler.runtime:
                    try:
                        tools.replace_in_file(filename, "/%s" % e, "/%s" % self.settings.compiler.runtime,
                                              strict=False)
                        self.output.warn("replace vs runtime %s in %s" % ("/%s" % e, filename))
                        replaced = True
                    except:
                        pass
            tools.replace_in_file(filename, "MDdd", "MDd", strict=False)
            tools.replace_in_file(filename, "MTdd", "MTd", strict=False)
            if not replaced:
                raise Exception("Could not find any vs runtime in file")

        replace_runtime_in_file("%s/Makefile" % self.subfolder)

    def visual_build(self):
        self.output.warn("----------CONFIGURING OPENSSL FOR WINDOWS. %s-------------" % self.version)
        target = self._get_target()
        no_asm = "no-asm" if self.options.no_asm else ""
        # Will output binaries to ./binaries
        with tools.vcvars(self.settings, filter_known_paths=False):

            config_command = "perl Configure %s %s --prefix=%s/binaries %s" % (target,
                                                                               no_asm,
                                                                               self.source_folder,
                                                                               self._get_flags())
            self.output.warn(config_command)
            self.run_in_src(config_command)
            self._patch_runtime()
            self.output.warn("----------MAKE OPENSSL %s-------------" % self.version)
            self.run_in_src("nmake build_libs")

    def package(self):
        # Copy the license files
        self.copy(src=self.subfolder, pattern="*LICENSE", keep_path=False)
        self.copy(pattern="*applink.c", dst="include/openssl/", keep_path=False)
        if self.settings.os == "Windows" and self.compiler == "Visual Studio":
            self.copy(pattern="*.lib", dst="lib", keep_path=False)
            self.copy(pattern="*.dll", dst="bin", keep_path=False)
            self.copy(pattern="*.h", dst="include/openssl/", src="binaries/include/", keep_path=False)
            if self.settings.build_type == 'Debug':
                with tools.chdir(os.path.join(self.package_folder, 'lib')):
                    os.rename('libssl.lib', 'libssld.lib')
                    os.rename('libcrypto.lib', 'libcryptod.lib')
        elif self.settings.os == "Windows" and self.compiler == "gcc":
            self.copy(src=self.subfolder, pattern="include/*", dst="include/openssl/", keep_path=False)
            if self.options.shared:
                self.copy(src=self.subfolder, pattern="*libcrypto.dll.a", dst="lib", keep_path=False)
                self.copy(src=self.subfolder, pattern="*libssl.dll.a", dst="lib", keep_path=False)
                self.copy(src=self.subfolder, pattern="*libcrypto*.dll", dst="bin", keep_path=False)
                self.copy(src=self.subfolder, pattern="*libssl*.dll", dst="bin", keep_path=False)
                self.copy(pattern="*.dll", dst="bin/engines", src="binaries/lib/engines", keep_path=True)
            else:
                self.copy(src=self.subfolder, pattern="*libcrypto.a", dst="lib", keep_path=False)
                self.copy(src=self.subfolder, pattern="*libssl.a", dst="lib", keep_path=False)
        else:
            if self.options.shared:
                self.copy(pattern="*libcrypto*.dylib", dst="lib", keep_path=False, symlinks=True)
                self.copy(pattern="*libssl*.dylib", dst="lib", keep_path=False, symlinks=True)
                self.copy(pattern="*.dylib", src=os.path.join(self.subfolder, "engines"),
                          dst="bin/engines", keep_path=True)
                self.copy(pattern="*libcrypto.so*", dst="lib", keep_path=False, symlinks=True)
                self.copy(pattern="*libssl.so*", dst="lib", keep_path=False, symlinks=True)
                self.copy(pattern="*.so", src=os.path.join(self.subfolder, "engines"),
                          dst="bin/engines", keep_path=True)
            else:
                self.copy("*.a", "lib", keep_path=False)

        self.copy(src=self.subfolder,
                  pattern="include/openssl/*.h",
                  dst="include/openssl",
                  keep_path=False)

    def package_info(self):
        if self.compiler == "Visual Studio":
            self.cpp_info.libs = ['libssld', 'libcryptod'] if self.settings.build_type == 'Debug' else \
                ['libssl', 'libcrypto']
        elif self.compiler == "gcc" and self.settings.os == "Windows":
            self.cpp_info.libs = ["ssl", "crypto"]
        elif self.settings.os == "Linux":
            self.cpp_info.libs = ["ssl", "crypto", "dl", "pthread"]
        else:
            self.cpp_info.libs = ["ssl", "crypto"]
        if self.settings.os == "Windows":
            self.cpp_info.libs.extend(["crypt32", "msi", "ws2_32", "advapi32", "user32"])
