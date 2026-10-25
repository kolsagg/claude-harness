#Requires -Version 5.1
<#
.SYNOPSIS
  GPTPro export, Windows PowerShell sürümü (export.sh ile aynı davranış).

.DESCRIPTION
  Repoyu mantıksal, node_modules'suz, gizli anahtarsız zip paketlerine böler; böylece
  ajan olmayan bir model (ChatGPT web arayüzündeki GPT Pro ya da dosya yüklenebilen
  herhangi bir sohbet modeli) kod tabanını parça parça gezebilir.

  zip ve rsync gerektirmez: kopyalama ve sıkıştırma .NET ile yapılır. bundles.conf
  bash ile "source" edilmez, satır satır ayrıştırılır; yalnız define_bundle satırları
  okunur. Ayarlar export.sh ile aynı ortam değişkenlerinden ya da parametrelerden gelir.

.EXAMPLE
  $env:PROJECT_ROOT = 'C:\dev\repo'; & ~/.claude/skills/gptpro/scripts/export.ps1

.EXAMPLE
  & export.ps1 -ProjectRoot C:\dev\repo -OutputDir $HOME\Desktop\review-bundles -AllowSecrets
#>
[CmdletBinding()]
param(
  [string]$ProjectRoot = $env:PROJECT_ROOT,
  [string]$OutputDir = $env:OUTPUT_DIR,
  [string]$BundlesConf = $env:BUNDLES_CONF,
  [string]$BundlePrefix = $env:BUNDLE_PREFIX,
  [switch]$AllowSecrets
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem

if (-not $ProjectRoot) { $ProjectRoot = (Get-Location).Path }
$allowSecretsOn = $AllowSecrets.IsPresent -or ($env:ALLOW_SECRETS -eq '1')

function Write-Log([string]$m)  { Write-Host "[gptpro] $m" }
function Write-Warn2([string]$m) { [Console]::Error.WriteLine("[gptpro] WARN: $m") }
# Otomatik algılamada eksik kaynak beklenen bir durumdur, uyarı basılmaz.
function Write-Soft([string]$m)  { if (-not $script:Autodetect) { Write-Warn2 $m } }
function Stop-Export([string]$m) { throw "GPTPRO_ABORT: $m" }

# Genel dışlamalar: bağımlılıklar, build çıktısı, önbellekler, gizli dosyalar, vcs, ikili dosyalar.
$GlobalExcludes = @(
  '.git', 'node_modules', '.next', '.turbo', 'dist', 'build', 'out', 'coverage', '.vercel',
  '*.tsbuildinfo', '.env', '.env.*', '*.log', '.DS_Store', 'Icon?',
  '*.png', '*.jpg', '*.jpeg', '*.gif', '*.webp', '*.avif', '*.ico', '*.mp4', '*.mov',
  '*.webm', '*.woff', '*.woff2', '*.ttf', '*.otf'
)

# rsync --exclude kalıbını kurala çevirir. Kalıp yol bileşeni sınırında eşleşir
# (eğik çizgisizse dosya/klasör adına, eğik çizgiliyse yolun sonuna); ** eğik çizgiyi de geçer.
# Baştaki / kaynağın köküne bağlar, sondaki / yalnız klasörlerle eşleştirir.
function ConvertTo-ExcludeRegex([string]$glob) {
  $dirOnly = $glob.EndsWith('/')
  if ($dirOnly) { $glob = $glob.TrimEnd('/') }
  $anchored = $glob.StartsWith('/')
  if ($anchored) { $glob = $glob.TrimStart('/') }
  $sb = New-Object System.Text.StringBuilder
  $i = 0
  while ($i -lt $glob.Length) {
    $c = $glob[$i]
    if ($c -eq '*' -and ($i + 1) -lt $glob.Length -and $glob[$i + 1] -eq '*') {
      if (($i + 2) -lt $glob.Length -and $glob[$i + 2] -eq '/') { [void]$sb.Append('(?:.*/)?'); $i += 3 }
      else { [void]$sb.Append('.*'); $i += 2 }
      continue
    }
    if ($c -eq '*') { [void]$sb.Append('[^/]*') }
    elseif ($c -eq '?') { [void]$sb.Append('[^/]') }
    else { [void]$sb.Append([regex]::Escape([string]$c)) }
    $i++
  }
  $prefix = if ($anchored) { '^' } else { '(?:^|/)' }
  [pscustomobject]@{
    Re      = New-Object System.Text.RegularExpressions.Regex ($prefix + $sb.ToString() + '$'), 'IgnoreCase'
    DirOnly = $dirOnly
  }
}

$GlobalExcludeRegexes = @($GlobalExcludes | ForEach-Object { ConvertTo-ExcludeRegex $_ })

function Test-Excluded([string]$rel, [bool]$isDir, $rules) {
  foreach ($r in $rules) {
    if ($r.DirOnly -and -not $isDir) { continue }
    if ($r.Re.IsMatch($rel)) { return $true }
  }
  return $false
}

# Klasörü dışlamaları uygulayarak kopyalar. Bağlantılara (symlink/junction) girmez ve
# bağlantı dosyalarını kopyalamaz: depo dışındaki bir dosyayı (ör. kimlik bilgisi) pakete taşıyabilirler.
function Copy-Tree([string]$src, [string]$dest, $regexes) {
  [void][IO.Directory]::CreateDirectory($dest)
  $stack = New-Object System.Collections.Stack
  $stack.Push(@($src, ''))
  while ($stack.Count -gt 0) {
    $node = $stack.Pop()
    foreach ($item in Get-ChildItem -LiteralPath $node[0] -Force) {
      $rel = if ($node[1]) { $node[1] + '/' + $item.Name } else { $item.Name }
      if (Test-Excluded $rel $item.PSIsContainer $regexes) { continue }
      if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { Write-Warn2 "skipping link: $rel"; continue }
      $target = Join-Path $dest ($rel -replace '/', '\')
      if ($item.PSIsContainer) {
        [void][IO.Directory]::CreateDirectory($target)
        $stack.Push(@($item.FullName, $rel))
      } else {
        [IO.File]::Copy($item.FullName, $target, $true)
      }
    }
  }
}

# Kökten kaynağa kadar her yol parçası denetlenir: aradaki bir bağlantı (junction/symlink)
# ön ek kontrolünü geçip depo dışını pakete taşıyabilir.
function Assert-NoLinkOnPath([string]$abs, [string]$name, [string]$path) {
  $root = $ProjectRoot.TrimEnd('\')
  if ($abs.Length -le $root.Length) { return }
  $cur = $root
  foreach ($part in $abs.Substring($root.Length).TrimStart('\').Split('\')) {
    $cur = Join-Path $cur $part
    if (-not (Test-Path -LiteralPath $cur)) { return }
    if ((Get-Item -LiteralPath $cur -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
      Stop-Export "source passes through a link in bundle '$name': $path"
    }
  }
}

$script:BundleNames = @()
$script:BundleDescs = @()

# Add-Bundle <ad> <açıklama> <kaynak>...
#   kaynaklar: dir:<yol>[:<ek-dışlama>] | file:<yol>[:<altklasör>]
function Add-Bundle([string]$name, [string]$desc, [string[]]$sources) {
  $staged = $false
  foreach ($src in $sources) {
    $idx = $src.IndexOf(':')
    if ($idx -lt 0) { Write-Warn2 "unknown source type '$src' in bundle '$name' (expected dir: or file:)"; continue }
    $kind = $src.Substring(0, $idx)
    $rest = $src.Substring($idx + 1)
    $sep = $rest.IndexOf(':')
    $path = if ($sep -ge 0) { $rest.Substring(0, $sep) } else { $rest }
    $extra = if ($sep -ge 0) { $rest.Substring($sep + 1) } else { '' }
    $abs = [IO.Path]::GetFullPath((Join-Path $ProjectRoot $path))
    $rootPrefix = $ProjectRoot.TrimEnd('\') + '\'
    if ($abs -ne $ProjectRoot.TrimEnd('\') -and -not $abs.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
      Stop-Export "source outside the project root in bundle '$name': $path"
    }
    Assert-NoLinkOnPath $abs $name $path
    switch ($kind) {
      'dir' {
        if (-not (Test-Path -LiteralPath $abs -PathType Container)) { Write-Soft "skipping missing dir for '$name': $path"; continue }
        $regexes = $GlobalExcludeRegexes
        if ($extra) { $regexes = $regexes + @(ConvertTo-ExcludeRegex $extra) }
        Copy-Tree $abs (Join-Path (Join-Path $TmpDir $name) (Split-Path -Leaf $abs)) $regexes
        $staged = $true
      }
      'file' {
        if (-not (Test-Path -LiteralPath $abs)) { Write-Soft "skipping missing file for '$name': $path"; continue }
        # Klasör dışlamasız kopyalanırdı (.env, node_modules); export.sh'teki cp de burada durur.
        if (Test-Path -LiteralPath $abs -PathType Container) { Stop-Export "file: source is a directory in bundle '$name': $path (use dir:)" }
        $destDir = Join-Path $TmpDir $name
        if ($extra) { $destDir = Join-Path $destDir ($extra -replace '/', '\') }
        [void][IO.Directory]::CreateDirectory($destDir)
        [IO.File]::Copy($abs, (Join-Path $destDir (Split-Path -Leaf $abs)), $true)
        $staged = $true
      }
      default { Write-Warn2 "unknown source type '$kind' in bundle '$name' (expected dir: or file:)" }
    }
  }
  if (-not $staged) { Write-Soft "bundle '$name' staged nothing — skipping"; return }
  $script:BundleNames += $name
  $script:BundleDescs += $desc
  Write-Log "staged $name"
}

# --- bundles.conf ayrıştırma -------------------------------------------------
# bash'in tırnak kuralının yeterli alt kümesi: tek/çift tırnak, ters bölü ile satır
# devamı, kelime başındaki # yorum. Değişken açılımı yapılmaz, komut çalıştırılmaz.
function Split-ShellWords([string]$s) {
  $words = New-Object System.Collections.Generic.List[string]
  $cur = New-Object System.Text.StringBuilder
  $inWord = $false
  $quote = [char]0
  for ($i = 0; $i -lt $s.Length; $i++) {
    $c = $s[$i]
    if ($quote -ne [char]0) {
      if ($c -eq $quote) { $quote = [char]0 } else { [void]$cur.Append($c) }
      continue
    }
    if ($c -eq [char]'"' -or $c -eq [char]"'") { $quote = $c; $inWord = $true; continue }
    if ([char]::IsWhiteSpace($c)) {
      if ($inWord) { $words.Add($cur.ToString()); [void]$cur.Clear(); $inWord = $false }
      continue
    }
    if ($c -eq [char]'#' -and -not $inWord) { break }
    [void]$cur.Append($c)
    $inWord = $true
  }
  if ($quote -ne [char]0) { Stop-Export "unterminated quote in bundles.conf: $s" }
  if ($inWord) { $words.Add($cur.ToString()) }
  return ,$words.ToArray()
}

function Import-BundlesConf([string]$path) {
  $buf = ''
  $commands = New-Object System.Collections.Generic.List[object]
  foreach ($raw in [IO.File]::ReadAllLines($path)) {
    $line = $raw.TrimEnd()
    if ($buf -eq '' -and $line.TrimStart().StartsWith('#')) { continue }
    if ($line.EndsWith('\')) { $buf += $line.Substring(0, $line.Length - 1) + ' '; continue }
    $buf += $line
    if ($buf.Trim()) { $commands.Add((Split-ShellWords $buf)) }
    $buf = ''
  }
  if ($buf.Trim()) { $commands.Add((Split-ShellWords $buf)) }
  foreach ($words in $commands) {
    if ($words.Count -eq 0) { continue }
    if ($words[0] -ne 'define_bundle') { Write-Warn2 "ignoring unsupported bundles.conf line: $($words -join ' ')"; continue }
    if ($words.Count -lt 3) { Write-Warn2 "define_bundle needs <name> <description>: $($words -join ' ')"; continue }
    $srcs = if ($words.Count -gt 3) { $words[3..($words.Count - 1)] } else { @() }
    Add-Bundle $words[1] $words[2] $srcs
  }
}

# --- otomatik algılama -------------------------------------------------------
# bundles.conf yoksa: her workspace paketi için bir paket (apps/*, packages/*, services/*,
# libs/*), yalnız şema içeren db paketi, docs paketi; tek paketli repoda src paketi.
function Invoke-Autodetect {
  $found = $false
  foreach ($parent in 'apps', 'packages', 'services', 'libs') {
    $p = Join-Path $ProjectRoot $parent
    if (-not (Test-Path -LiteralPath $p -PathType Container)) { continue }
    $dirs = Get-ChildItem -LiteralPath $p -Directory | Where-Object { -not $_.Name.StartsWith('.') } | Sort-Object Name
    foreach ($d in $dirs) {
      Add-Bundle $d.Name "$parent/$($d.Name) — workspace package" @("dir:$parent/$($d.Name)")
      $found = $true
    }
  }
  if (-not $found) {
    Add-Bundle 'src' 'application source' @(
      'dir:src', 'dir:lib', 'dir:app', 'dir:test', 'dir:tests',
      'file:package.json', 'file:tsconfig.json', 'file:pyproject.toml', 'file:go.mod', 'file:Cargo.toml')
  }
  # Yalnız şema yapısı; asla satır ya da seed verisi değil.
  Add-Bundle 'db' 'database architecture: migrations and schema map (no rows)' @(
    'dir:supabase/migrations', 'dir:migrations', 'dir:db/migrations', 'dir:prisma',
    'file:supabase/config.toml:supabase')
  Add-Bundle 'docs' 'architecture, ADRs, and conventions' @(
    'dir:docs', 'dir:adrs', 'dir:doc', 'dir:prds',
    'file:README.md', 'file:AGENTS.md', 'file:CLAUDE.md', 'file:pnpm-workspace.yaml', 'file:package.json')
}

# --- gizli anahtar taraması --------------------------------------------------
# Paketler üçüncü taraf bir sohbet arayüzüne yüklenecek; elle kontrol etmeyi
# hatırlaman gereken bir paket güvenli değildir. İki kademe, export.sh ile aynı:
#   HARD — sağlayıcıların verdiği anahtar biçimleri. Export'u durdurur.
#   SOFT — genel `secret = "..."` atamaları. Yalnız gösterilir.
# Test dosyaları ve açık yer tutucular SOFT'a düşürülür.
# export.sh ikili dosyaları atlar (grep -I). Windows PowerShell 5.1 metni varsayılan olarak
# UTF-16 yazdığı için burada hiçbir dosya atlanmaz: UTF-16 çözülür, gerçek ikili dosya
# Latin-1 olarak okunur ve içindeki ASCII anahtarlar da yakalanır.
function Read-ScanLines([string]$path) {
  $bytes = [IO.File]::ReadAllBytes($path)
  $enc = $null
  if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) { $enc = [Text.Encoding]::Unicode }
  elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) { $enc = [Text.Encoding]::BigEndianUnicode }
  else {
    $n = [Math]::Min($bytes.Length, 8000)
    $evenNul = 0; $oddNul = 0
    for ($i = 0; $i -lt $n; $i++) {
      if ($bytes[$i] -eq 0) { if ($i % 2 -eq 0) { $evenNul++ } else { $oddNul++ } }
    }
    $half = [Math]::Max(1, [int]($n / 2))
    if ($oddNul -gt $half * 0.3 -and $evenNul -lt $half * 0.05) { $enc = [Text.Encoding]::Unicode }
    elseif ($evenNul -gt $half * 0.3 -and $oddNul -lt $half * 0.05) { $enc = [Text.Encoding]::BigEndianUnicode }
    elseif (($evenNul + $oddNul) -gt 0) {
      # Karışık ikili dosya: Latin-1 ASCII dizgileri, NUL'ları atılmış kopya da ikili dosyaya
      # gömülü UTF-16 dizgileri (exe/dll kaynakları) okunur hale getirir.
      $latin = [Text.Encoding]::GetEncoding(28591).GetString($bytes)
      return ,(($latin -split "`r?`n|`0") + ($latin.Replace("`0", '') -split "`r?`n"))
    }
    else { $enc = New-Object Text.UTF8Encoding $false }
  }
  $text = $enc.GetString($bytes)
  if ($text.Length -gt 0 -and $text[0] -eq [char]0xFEFF) { $text = $text.Substring(1) }
  return ,($text -split "`r?`n|`0")
}

# Bulunan değer çıktıya tam basılmaz: script'i çalıştıran ajanın kaydına anahtar düşmesin.
# İlk 6 karakter türü gösterir (ghp_, AKIA, sk-ant), gerisi uzunlukla özetlenir.
function Get-MaskedValue([string]$value) {
  $keep = [Math]::Min(6, $value.Length)
  return $value.Substring(0, $keep) + '...[' + $value.Length + ' chars]'
}

function Invoke-SecretScan {
  $hard = 'BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|sk-ant-[A-Za-z0-9_-]{40,}|sk-[A-Za-z0-9]{40,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|xox[baprs]-[A-Za-z0-9-]{20,}|AIza[0-9A-Za-z_-]{30,}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.'
  $soft = '(password|passwd|secret|api_?key|access_?token)\s*[=:]\s*["''][^"''\s]{8,}'
  $fixture = 'FAKE|EXAMPLE|PLACEHOLDER|DUMMY|REDACTED|SAMPLE|NOT_?A_?REAL|xxxxxxxx|XXXXXXXX|0123456789|abcdefghij|env\('
  $testpath = '/(test|tests|__tests__|fixtures|spec)/|\.(test|spec)\.[a-z]+:'

  $hardRe = New-Object System.Text.RegularExpressions.Regex $hard
  $softRe = New-Object System.Text.RegularExpressions.Regex $soft
  $softHits = New-Object System.Collections.Generic.List[string]
  $hardHits = New-Object System.Collections.Generic.List[string]
  $rootLen = $TmpDir.TrimEnd('\').Length + 1

  foreach ($f in Get-ChildItem -LiteralPath $TmpDir -Recurse -Force -File) {
    $rel = $f.FullName.Substring($rootLen) -replace '\\', '/'
    $lineNo = 0
    foreach ($line in (Read-ScanLines $f.FullName)) {
      $lineNo++
      # HARD satırın tamamında ayrı geçişle aranır: tek birleşik regex'te SOFT eşleşmesi
      # (ör. `secret: "-----BEGIN`) HARD'ın başlangıcını yutup özel anahtarı gizliyordu.
      foreach ($m in $hardRe.Matches($line)) {
        $hit = "${rel}:${lineNo}:$(Get-MaskedValue $m.Value)"
        $softHits.Add($hit)
        # Yer tutucu işareti yalnız eşleşen değerde aranır (yolda değil: `examples/` klasörü
        # gerçek anahtarı düşürmesin); test yolu ayrı ve açık bir karardır.
        if (($m.Value -cnotmatch $fixture) -and ("/${rel}:" -cnotmatch $testpath)) { $hardHits.Add($hit) }
      }
      foreach ($m in $softRe.Matches($line)) {
        $softHits.Add("${rel}:${lineNo}:$(Get-MaskedValue $m.Value)")
      }
    }
  }

  if ($softHits.Count -gt 0) {
    [Console]::Error.WriteLine("`n[gptpro] credential-shaped strings found (review, not fatal):")
    $softHits | Select-Object -First 25 | ForEach-Object { [Console]::Error.WriteLine($_) }
    [Console]::Error.WriteLine('')
  }

  if ($hardHits.Count -gt 0) {
    [Console]::Error.WriteLine("`n[gptpro] LIVE-LOOKING CREDENTIALS — export aborted:`n")
    $hardHits | ForEach-Object { [Console]::Error.WriteLine($_) }
    [Console]::Error.WriteLine('')
    if ($allowSecretsOn) {
      Write-Warn2 'ALLOW_SECRETS=1 set — continuing anyway. Verify every hit above is a fixture.'
    } else {
      Stop-Export 'refusing to build bundles. Remove the values, or re-run with -AllowSecrets (ALLOW_SECRETS=1) if these are fixtures.'
    }
  } else {
    Write-Log 'secret scan clean (no live-looking credentials)'
  }
}

# Zip girdileri eğik çizgiyle yazılır (Compress-Archive 5.1'de ters bölü yazabiliyor).
function New-BundleZip([string]$name) {
  $root = Join-Path $TmpDir $name
  # Önce geçici klasöre yazılır; yarıda kesilen çalışma çıktı klasöründe yarım zip bırakmaz.
  $zipPath = Join-Path $ZipStage "$BundlePrefix-$name.zip"
  $fs = [IO.File]::Open($zipPath, [IO.FileMode]::Create)
  try {
    $zip = New-Object System.IO.Compression.ZipArchive($fs, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
      [void]$zip.CreateEntry("$name/")
      $rootLen = $root.TrimEnd('\').Length + 1
      foreach ($item in Get-ChildItem -LiteralPath $root -Recurse -Force) {
        $entry = "$name/" + ($item.FullName.Substring($rootLen) -replace '\\', '/')
        if ($item.PSIsContainer) { [void]$zip.CreateEntry("$entry/") }
        else { [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $item.FullName, $entry, [System.IO.Compression.CompressionLevel]::Optimal) }
      }
    } finally { $zip.Dispose() }
  } finally { $fs.Dispose() }
}

$exitCode = 0
# Benzersiz ad: yarıda kesilmiş eski bir çalışmanın artığına yazılmaz.
$TmpDir = Join-Path ([IO.Path]::GetTempPath()) ("gptpro-export-$PID-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
try {
  if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) { Stop-Export "PROJECT_ROOT does not exist: $ProjectRoot" }
  $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
  if (-not $OutputDir) { $OutputDir = Join-Path $ProjectRoot 'gptpro-bundles' }
  if (-not $BundlesConf) { $BundlesConf = Join-Path (Split-Path -Parent $PSScriptRoot) 'bundles.conf' }
  if (-not $BundlePrefix) { $BundlePrefix = Split-Path -Leaf $ProjectRoot }
  $script:Autodetect = $false

  Write-Log "project: $ProjectRoot"
  Write-Log "output:  $OutputDir"
  [void][IO.Directory]::CreateDirectory($OutputDir)
  $OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path
  [void][IO.Directory]::CreateDirectory($TmpDir)
  $ZipStage = $TmpDir + '-zips'
  [void][IO.Directory]::CreateDirectory($ZipStage)
  # Yalnız bu önekin eski paketleri silinir; çıktı klasörü Masaüstü gibi ortak bir yer olabilir.
  Get-ChildItem -LiteralPath $OutputDir -Filter "$BundlePrefix-*.zip" -File | Remove-Item -Force

  # El yazımı bundles.conf her zaman kazanır; yoksa otomatik algılamaya düşülür.
  if (Test-Path -LiteralPath $BundlesConf -PathType Leaf) {
    Write-Log "bundles: $BundlesConf"
    Import-BundlesConf $BundlesConf
  } else {
    Write-Log 'no bundles.conf — autodetecting layout (write one for a better split)'
    $script:Autodetect = $true
    Invoke-Autodetect
  }

  if ($script:BundleNames.Count -eq 0) { Stop-Export "no bundles staged — check $BundlesConf against your repo layout" }

  Invoke-SecretScan

  foreach ($name in $script:BundleNames) { New-BundleZip $name }
  foreach ($z in Get-ChildItem -LiteralPath $ZipStage -Filter '*.zip' -File) {
    Move-Item -LiteralPath $z.FullName -Destination (Join-Path $OutputDir $z.Name) -Force
  }

  Write-Log 'done'
  Get-ChildItem -LiteralPath $OutputDir -Filter "$BundlePrefix-*.zip" -File | Sort-Object Name | ForEach-Object {
    Write-Host ('{0,10:N1} KB  {1}' -f ($_.Length / 1KB), $_.FullName)
  }

  Write-Host ("`nSummary ({0}, node_modules-free, secret-scanned):" -f $BundlePrefix)
  for ($i = 0; $i -lt $script:BundleNames.Count; $i++) {
    Write-Host ("- {0}-{1}.zip : {2}" -f $BundlePrefix, $script:BundleNames[$i], $script:BundleDescs[$i])
  }
} catch {
  $msg = $_.Exception.Message -replace '^GPTPRO_ABORT: ', ''
  [Console]::Error.WriteLine("[gptpro] ERROR: $msg")
  $exitCode = 1
} finally {
  foreach ($d in $TmpDir, ($TmpDir + '-zips')) {
    if (Test-Path -LiteralPath $d) { Remove-Item -LiteralPath $d -Recurse -Force }
  }
}
exit $exitCode
