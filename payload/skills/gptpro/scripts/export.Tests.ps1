#Requires -Version 5.1
# export.ps1 için duman testleri. Pester gerektirmez:
#   powershell -NoProfile -File export.Tests.ps1
# Her senaryo geçici bir sahte repo kurar, export.ps1'i ayrı süreçte çalıştırır,
# çıkış kodunu ve zip içeriğini kontrol eder.

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

$Script = Join-Path $PSScriptRoot 'export.ps1'
$Work = Join-Path ([IO.Path]::GetTempPath()) "gptpro-tests-$PID"
$script:Failures = 0
$script:Passes = 0

function Assert([bool]$cond, [string]$what) {
  if ($cond) { $script:Passes++; Write-Host "  ok   $what" }
  else { $script:Failures++; Write-Host "  FAIL $what" -ForegroundColor Red }
}

function New-File([string]$root, [string]$rel, [string]$content = 'x') {
  $p = Join-Path $root ($rel -replace '/', '\')
  [void][IO.Directory]::CreateDirectory((Split-Path -Parent $p))
  [IO.File]::WriteAllText($p, $content)
}

function Invoke-Export([string]$root, [string[]]$extraArgs = @()) {
  $out = Join-Path $root '..\out'
  $conf = Join-Path $root 'bundles.conf'
  $args2 = @('-NoProfile', '-File', $Script, '-ProjectRoot', $root, '-OutputDir', $out, '-BundlesConf', $conf, '-BundlePrefix', 't') + $extraArgs
  # stderr satırları 5.1'de hata kaydına sarılır; Stop tercihi bunları fırlatmasın.
  $ErrorActionPreference = 'Continue'
  $log = & powershell.exe @args2 2>&1 | ForEach-Object { "$_" } | Out-String
  [pscustomobject]@{ Code = $LASTEXITCODE; Log = $log; Out = $out }
}

function Get-ZipEntries([string]$zip) {
  $z = [IO.Compression.ZipFile]::OpenRead($zip)
  try { return @($z.Entries | ForEach-Object { $_.FullName }) } finally { $z.Dispose() }
}

# Gerçek görünen anahtar test dosyasına düz yazılmaz, çalışırken üretilir.
$LiveToken = 'gh' + 'p_' + ('Q7w' * 12)

function New-Monorepo([string]$root) {
  New-File $root 'apps/web/src/a.ts' 'export const a = 1'
  New-File $root 'apps/web/node_modules/dep/index.js'
  New-File $root 'apps/web/.env' 'TOKEN=abc'
  New-File $root 'apps/web/logo.png'
  New-File $root 'apps/web/.eslintrc.json' '{}'
  New-File $root "apps/web/test/key.test.ts" "const t = '$LiveToken'"
  New-File $root 'apps/web/dist/bundle.js'
  New-File $root 'packages/core/src/core.ts' 'export {}'
  New-File $root 'packages/core/test/__snapshots__/s.snap'
  New-File $root 'packages/core/test/core.test.ts'
  New-File $root 'docs/arch.md' '# arch'
  New-File $root 'supabase/migrations/001.sql' 'create table t();'
  New-File $root 'supabase/config.toml' 'x=1'
  New-File $root 'README.md' '# repo'
}

try {
  Write-Host 'S1: monorepo, otomatik algılama'
  $r = Join-Path $Work 's1\repo'; New-Monorepo $r
  $tmpBefore = @(Get-ChildItem ([IO.Path]::GetTempPath()) -Filter 'gptpro-export-*' | ForEach-Object { $_.Name })
  $res = Invoke-Export $r
  Assert ($res.Code -eq 0) "çıkış kodu 0 (gelen: $($res.Code))"
  $zips = @(Get-ChildItem $res.Out -Filter *.zip | ForEach-Object { $_.Name } | Sort-Object)
  Assert (($zips -join ',') -eq 't-core.zip,t-db.zip,t-docs.zip,t-web.zip') "paketler core/db/docs/web (gelen: $($zips -join ','))"
  $web = Get-ZipEntries (Join-Path $res.Out 't-web.zip')
  Assert ($web -contains 'web/web/src/a.ts') 'web kaynak dosyası var'
  Assert ($web -contains 'web/web/.eslintrc.json') 'nokta ile başlayan yapılandırma dosyası var'
  Assert ($web -contains 'web/web/test/key.test.ts') 'testler korunuyor'
  Assert (-not ($web -match 'node_modules|\.env$|\.png$|/dist/')) 'node_modules, .env, png, dist dışlandı'
  Assert (-not ($web -match '\\')) 'zip girdilerinde ters bölü yok'
  $db = Get-ZipEntries (Join-Path $res.Out 't-db.zip')
  Assert ($db -contains 'db/migrations/001.sql') 'db paketinde migration var'
  Assert ($db -contains 'db/supabase/config.toml') 'config.toml supabase/ altında'
  Assert ($res.Log -match 'credential-shaped') 'test içindeki anahtar SOFT olarak gösterildi'
  $tmpNew = @(Get-ChildItem ([IO.Path]::GetTempPath()) -Filter 'gptpro-export-*' | Where-Object { $tmpBefore -notcontains $_.Name })
  Assert ($tmpNew.Count -eq 0) 'geçici klasör temizlendi'

  Write-Host 'S2: kaynak koddaki canlı anahtar export''u durdurur'
  $r = Join-Path $Work 's2\repo'; New-Monorepo $r
  New-File $r 'packages/core/src/k.ts' "const k = '$LiveToken'"
  New-File (Join-Path $Work 's2\out') 't-stale.zip'
  $res = Invoke-Export $r
  Assert ($res.Code -eq 1) "çıkış kodu 1 (gelen: $($res.Code))"
  Assert ($res.Log -match 'LIVE-LOOKING CREDENTIALS') 'HARD uyarısı basıldı'
  Assert ($res.Log -match 'core/core/src/k\.ts:1:') 'dosya ve satır gösterildi'
  Assert (-not $res.Log.Contains($LiveToken)) 'anahtarın tamamı çıktıya basılmadı'
  Assert (-not $res.Log.Contains($LiveToken.Substring(0, 12))) 'anahtarın ilk 12 karakteri de basılmadı'
  Assert (@(Get-ChildItem $res.Out -Filter *.zip).Count -eq 0) 'hiç zip üretilmedi, eski zip silindi'

  Write-Host 'S3: -AllowSecrets ile devam eder'
  $res = Invoke-Export $r @('-AllowSecrets')
  Assert ($res.Code -eq 0) "çıkış kodu 0 (gelen: $($res.Code))"
  Assert ($res.Log -match 'continuing anyway') 'devam uyarısı basıldı'

  Write-Host 'S4: bundles.conf, ek dışlama ve alt klasör'
  $r = Join-Path $Work 's4\repo'; New-Monorepo $r
  $conf = @'
# yorum satırı
define_bundle core "domain logic — en önemli paket" \
  dir:packages/core:test/**/__snapshots__

define_bundle db 'schema only' \
  dir:supabase/migrations \
  file:supabase/config.toml:supabase \
  dir:yok/boyle/bir/klasor   # eksik kaynak uyarı verir, durdurmaz
'@
  [IO.File]::WriteAllText((Join-Path $r 'bundles.conf'), $conf, (New-Object Text.UTF8Encoding $false))
  $res = Invoke-Export $r
  Assert ($res.Code -eq 0) "çıkış kodu 0 (gelen: $($res.Code))"
  $zips = @(Get-ChildItem $res.Out -Filter *.zip | ForEach-Object { $_.Name } | Sort-Object)
  Assert (($zips -join ',') -eq 't-core.zip,t-db.zip') "yalnız conf'taki paketler (gelen: $($zips -join ','))"
  $core = Get-ZipEntries (Join-Path $res.Out 't-core.zip')
  Assert (-not ($core -match '__snapshots__')) 'ek dışlama snapshot klasörünü attı'
  Assert ($core -contains 'core/core/test/core.test.ts') 'diğer testler duruyor'
  Assert ($res.Log -match "skipping missing dir for 'db'") 'eksik kaynak uyarısı'
  Assert ($res.Log -match 'en önemli paket') 'tırnaklı Türkçe açıklama korundu'

  Write-Host 'S5: tek paketli repo'
  $r = Join-Path $Work 's5\repo'
  New-File $r 'src/main.py' 'print(1)'
  New-File $r 'pyproject.toml' '[project]'
  $res = Invoke-Export $r
  Assert ($res.Code -eq 0) "çıkış kodu 0 (gelen: $($res.Code))"
  $src = Get-ZipEntries (Join-Path $res.Out 't-src.zip')
  Assert ($src -contains 'src/src/main.py') 'src paketi kaynak dosyayı içeriyor'
  Assert ($src -contains 'src/pyproject.toml') 'pyproject.toml paket kökünde'
  Write-Host 'S6: file: kaynağı klasörü gösterirse export durur'
  $r = Join-Path $Work 's6\repo'
  New-File $r 'cfg/.env' 'DATABASE_URL=postgres://u:p@h/db'
  New-File $r 'cfg/node_modules/x.js'
  [IO.File]::WriteAllText((Join-Path $r 'bundles.conf'), "define_bundle c `"cfg`" file:cfg`n")
  $res = Invoke-Export $r
  Assert ($res.Code -eq 1) "çıkış kodu 1 (gelen: $($res.Code))"
  Assert ($res.Log -match "file: source is a directory") 'klasör hatası basıldı'
  Assert (@(Get-ChildItem $res.Out -Filter *.zip -ErrorAction SilentlyContinue).Count -eq 0) 'zip üretilmedi'

  Write-Host 'S7: UTF-16 ve ikili dosyadaki anahtar da yakalanır'
  $r = Join-Path $Work 's7\repo'
  $aws = 'AK' + 'IA' + ('Q7W2' * 4)
  New-File $r 'src/ok.ts' 'export {}'
  [void][IO.Directory]::CreateDirectory((Join-Path $r 'src'))
  [IO.File]::WriteAllText((Join-Path $r 'src\u16bom.txt'), "k = $aws", [Text.Encoding]::Unicode)
  $res = Invoke-Export $r
  Assert ($res.Code -eq 1) "UTF-16 BOM'lu dosya: çıkış kodu 1 (gelen: $($res.Code))"
  Remove-Item (Join-Path $r 'src\u16bom.txt')
  [IO.File]::WriteAllBytes((Join-Path $r 'src\u16nobom.txt'), [Text.Encoding]::Unicode.GetBytes("k = $aws"))
  $res = Invoke-Export $r
  Assert ($res.Code -eq 1) "BOM'suz UTF-16: çıkış kodu 1 (gelen: $($res.Code))"
  Remove-Item (Join-Path $r 'src\u16nobom.txt')
  $bin = [byte[]](@(0, 1, 2, 0) + [Text.Encoding]::ASCII.GetBytes("k=$aws") + @(0, 0))
  [IO.File]::WriteAllBytes((Join-Path $r 'src\blob.dat'), $bin)
  $res = Invoke-Export $r
  Assert ($res.Code -eq 1) "ikili dosyada ASCII anahtar: çıkış kodu 1 (gelen: $($res.Code))"

  Remove-Item (Join-Path $r 'src\blob.dat')
  $u16 = [Text.Encoding]::Unicode.GetBytes("k=$aws")
  [IO.File]::WriteAllBytes((Join-Path $r 'src\res.bin'), [byte[]](@(0x4D, 0x5A, 0x90, 0, 3, 0, 0, 0, 4, 0, 0, 0, 0xFF, 0xFF) + $u16 + @(0x13, 0x37, 0xC3, 0xA9)))
  $res = Invoke-Export $r
  Assert ($res.Code -eq 1) "ikili dosyada UTF-16 anahtar: çıkış kodu 1 (gelen: $($res.Code))"
  Remove-Item (Join-Path $r 'src\res.bin')
  $pk = '-----BEGIN RSA ' + 'PRIVATE KEY-----'
  New-File $r 'src/tls.yaml' "tls_secret: `"$pk\nMIIE`""
  $res = Invoke-Export $r
  Assert ($res.Code -eq 1) "SOFT anahtarın arkasındaki özel anahtar: çıkış kodu 1 (gelen: $($res.Code))"

  Remove-Item (Join-Path $r 'src\tls.yaml')
  New-File $r 'src/EXAMPLE_0123456789/k.ts' "const k = '$LiveToken'"
  $res = Invoke-Export $r
  Assert ($res.Code -eq 1) "yolu yer tutucu kelime içeren dosyadaki anahtar: çıkış kodu 1 (gelen: $($res.Code))"

  Write-Host 'S10: kaynak kökten dışarı çıkamaz'
  $r = Join-Path $Work 's10\repo'
  New-File $r 'src/a.ts'
  New-File (Join-Path $Work 's10') 'outside/secret.txt'
  [IO.File]::WriteAllText((Join-Path $r 'bundles.conf'), "define_bundle x `"x`" dir:../outside`n")
  $res = Invoke-Export $r
  Assert ($res.Code -eq 1) "../ kaynağı: çıkış kodu 1 (gelen: $($res.Code))"
  Assert ($res.Log -match 'outside the project root') 'kök dışı hatası basıldı'

  Write-Host 'S11: yoldaki ara klasör bağlantıysa kaynak reddedilir'
  $r = Join-Path $Work 's11\repo'
  New-File $r 'src/a.ts'
  New-File (Join-Path $Work 's11') 'outside/sub/secret.txt'
  New-File (Join-Path $Work 's11') 'outside/pkg/x.ts'
  [void](New-Item -ItemType Junction -Path (Join-Path $r 'lnk') -Target (Join-Path $Work 's11\outside'))
  [IO.File]::WriteAllText((Join-Path $r 'bundles.conf'), "define_bundle x `"x`" dir:lnk/sub`n")
  $res = Invoke-Export $r
  Assert ($res.Code -eq 1) "ara bağlantılı kaynak: çıkış kodu 1 (gelen: $($res.Code))"
  Assert ($res.Log -match 'passes through a link') 'bağlantı hatası basıldı'
  Remove-Item (Join-Path $r 'bundles.conf')
  [void](New-Item -ItemType Junction -Path (Join-Path $r 'apps') -Target (Join-Path $Work 's11\outside'))
  $res = Invoke-Export $r
  Assert ($res.Code -eq 1) "otomatik algılamada bağlantı olan apps/: çıkış kodu 1 (gelen: $($res.Code))"

  Write-Host 'S8: kökten bağlı (/x) ve yalnız klasör (x/) dışlamaları'
  $r = Join-Path $Work 's8\repo'
  New-File $r 'app/secrets/a.txt'
  New-File $r 'app/deep/secrets/b.txt'
  New-File $r 'app/priv/c.txt'
  New-File $r 'app/sub/priv'
  $conf = "define_bundle a `"a`" dir:app:/secrets`ndefine_bundle b `"b`" dir:app:priv/`n"
  [IO.File]::WriteAllText((Join-Path $r 'bundles.conf'), $conf)
  $res = Invoke-Export $r
  Assert ($res.Code -eq 0) "çıkış kodu 0 (gelen: $($res.Code))"
  $a = Get-ZipEntries (Join-Path $res.Out 't-a.zip')
  Assert (-not ($a -contains 'a/app/secrets/a.txt')) '/secrets kökteki klasörü attı'
  Assert ($a -contains 'a/app/deep/secrets/b.txt') '/secrets alt klasördekine dokunmadı'
  $b = Get-ZipEntries (Join-Path $res.Out 't-b.zip')
  Assert (-not ($b -contains 'b/app/priv/c.txt')) 'priv/ klasörü attı'
  Assert ($b -contains 'b/app/sub/priv') 'priv/ aynı adlı dosyaya dokunmadı'

  Write-Host 'S9: çıktı klasöründe yalnız kendi önekli zip''ler silinir'
  $r = Join-Path $Work 's9\repo'
  New-File $r 'src/a.ts'
  New-File (Join-Path $Work 's9\out') 'baska.zip'
  New-File (Join-Path $Work 's9\out') 't-eski.zip'
  $res = Invoke-Export $r
  Assert (Test-Path (Join-Path $res.Out 'baska.zip')) 'başka zip korundu'
  Assert (-not (Test-Path (Join-Path $res.Out 't-eski.zip'))) 'eski önekli zip silindi'
} finally {
  if (Test-Path $Work) { Remove-Item $Work -Recurse -Force }
}

Write-Host ("`n{0} geçti, {1} kaldı" -f $script:Passes, $script:Failures)
if ($script:Failures -gt 0) { exit 1 }
