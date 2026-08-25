const path = require("node:path");
const { rcedit } = require("rcedit");

module.exports = async function afterPack(context) {
  if (context.electronPlatformName !== "win32") return;
  const version = context.packager.appInfo.version;
  const executable = path.join(context.appOutDir, "mLib.exe");
  await rcedit(executable, {
    icon: path.join(__dirname, "build", "icon.ico"),
    "file-version": version,
    "product-version": version,
    "version-string": {
      CompanyName: "mLib",
      FileDescription: "mLib — локальная медиатека",
      InternalName: "mLib",
      LegalCopyright: "Copyright © mLib contributors",
      OriginalFilename: "mLib.exe",
      ProductName: "mLib",
    },
    "requested-execution-level": "asInvoker",
  });
};
