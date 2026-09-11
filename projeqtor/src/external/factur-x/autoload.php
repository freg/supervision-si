<?php
spl_autoload_register(function ($class) {
  $map = [
      // atgp/factur-x
      'Atgp\\FacturX\\' => __DIR__ . '/factur-x-master/src/',
      
      // Smalot pdfparser
      'Smalot\\PdfParser\\' => __DIR__ . '/pdfparser/src/Smalot/PdfParser/',
      
      // FPDI
      'setasign\\Fpdi\\' => __DIR__ . '/FPDI/src/',
      
      // FPDF namespaced si besoin
      'FPDF\\' => __DIR__ . '/FPDF/src/',
  ];
  
  foreach ($map as $prefix => $baseDir) {
    if (strncmp($class, $prefix, strlen($prefix)) !== 0) continue;
    
    $relativeClass = substr($class, strlen($prefix));
    $file = $baseDir . str_replace('\\', '/', $relativeClass) . '.php';
    
    if (file_exists($file)) {
      require_once $file;
    }
    return;
  }
  
  // Cas classe globale FPDF
  if ($class === 'FPDF') {
    $fpdf = __DIR__ . '/FPDF/fpdf.php';
    if (file_exists($fpdf)) {
      require_once $fpdf;
    }
  }
});