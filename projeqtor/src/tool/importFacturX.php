<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 *
 * ProjeQtOr is free software: you can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option)
 * any later version.
 *
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/

require_once "../tool/projeqtor.php";

header('Content-Type: text/html; charset=UTF-8');

try {
  if (!isset($_FILES['pdfFacturxExtract']) || $_FILES['pdfFacturxExtract']['error'] !== UPLOAD_ERR_OK) {
    throw new Exception(i18n("noFileSelected"));
  }
  
  $tmp = $_FILES['pdfFacturxExtract']['tmp_name'];
  $pdfBinary = file_get_contents($tmp);
  
  $originalName = $_FILES['pdfFacturxExtract']['name'] ?? '';
  $extension = strtolower(pathinfo($originalName, PATHINFO_EXTENSION));
  if ($extension !== 'pdf') {
    throw new Exception(i18n("importFacturXNoPDF"));
  }
  
  // Factur-X lib gestion
  global $hideAutoloadError;
  $hideAutoloadError = true;
  require_once '../external/factur-x/autoload.php';
  
  //extract
  $reader = new \Atgp\FacturX\Reader();
  $xml = $reader->extractXML($pdfBinary);
  
  if (!$xml) {
    throw new Exception(i18n("importFacturXNoXML"));
  }
  
  //Valid XSD
  $validator = new \Atgp\FacturX\XsdValidator();
  $validator->validateWithException($xml);
  
  //Parser XML (EN16931) into array usable
  $data = parseFacturXEn16931($xml);
  
  // create ProviderBill
  $idProvider = findOrCreateProviderFromFacturX($data);
  $bill = createProviderBillFromFacturX($data, $idProvider);
  createProviderBillLines($data, $bill);

  $newId = (int)$bill->id;
  $newClass = 'ProviderBill';
  
  echo "<html><body><script>
  (function(){
    var objTop = window.top;
        
    try { if (objTop && objTop.hideWait) objTop.hideWait(); } catch(e) {}
    try { if (objTop && objTop.dijit) objTop.dijit.byId('dialogImportFacturX').hide(); } catch(e) {}
    try { if (objTop && objTop.showInfo) objTop.showInfo('Import Factur-X OK'); } catch(e) {}
        
    var objectClass = ".json_encode($newClass).";
    var objectId = ".json_encode($newId).";

    try {
      objTop.gotoElement(objectClass, objectId,null,true);
    } catch(e) {
      try { objTop.location.href = url; } catch(e2) {}
    }
    })();
  </script></body></html>";
  exit;
  
} catch (Throwable $e) {
  // Erreur return
  $msg = htmlspecialchars($e->getMessage(), ENT_QUOTES, 'UTF-8');
  echo "<html><body><script>
    try { if (window.top && window.top.hideWait) window.top.hideWait(); } catch(e) {}
    try {
      if (window.top && window.top.showAlert) window.top.showAlert('Import Factur-X : $msg');
      else alert('Import Factur-X : $msg');
    } catch(e) { alert('Import Factur-X : $msg'); }
  </script></body></html>";
  exit;
}

// ---------------------------
// Parser EN16931 
// Get an XML in enter to convert im in array
// ---------------------------
function parseFacturXEn16931(string $xml): array {
  $dom = new DOMDocument();
  $dom->loadXML($xml);
  
  $xp = new DOMXPath($dom);
  $xp->registerNamespace('rsm', 'urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100');
  $xp->registerNamespace('ram', 'urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100');
  $xp->registerNamespace('udt', 'urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100');
  $xp->registerNamespace('qdt', 'urn:un:unece:uncefact:data:standard:QualifiedDataType:100');
  
  // Helpers
  $t = fn(string $q) => xpathText($xp, $q);
  $a = fn(string $q, string $attr) => xpathAttr($xp, $q, $attr);
  
  $res = [
      'context' => [
          'guideline' => $t('//rsm:ExchangedDocumentContext/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID'),
      ],
      'document' => [
          'id'        => $t('//rsm:ExchangedDocument/ram:ID'),
          'typeCode'  => $t('//rsm:ExchangedDocument/ram:TypeCode'),
          'issueDate' => normalizeDate($t('//rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString')),
          'notes'     => [],
      ],
      'order' => [
          'buyerOrderRef' => $t('//ram:ApplicableHeaderTradeAgreement/ram:BuyerOrderReferencedDocument/ram:IssuerAssignedID'),
      ],
      'delivery' => [
          'actualDeliveryDate' => normalizeDate($t('//ram:ApplicableHeaderTradeDelivery/ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime/udt:DateTimeString')),
      ],
      'currency' => $t('//ram:ApplicableHeaderTradeSettlement/ram:InvoiceCurrencyCode'),
      'seller' => [
          'name'   => $t('//ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:Name'),
          'siret'  => $t('//ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:SpecifiedLegalOrganization/ram:ID'),
          'vat'    => firstMatchingTaxId($xp, '//ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID[@schemeID="VA"]'),
          'taxIds' => xpathTexts($xp, '//ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID'),
          'address' => [
              'postcode' => $t('//ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:PostalTradeAddress/ram:PostcodeCode'),
              'line1'    => $t('//ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:PostalTradeAddress/ram:LineOne'),
              'city'     => $t('//ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:PostalTradeAddress/ram:CityName'),
              'country'  => $t('//ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:PostalTradeAddress/ram:CountryID'),
          ],
      ],
      'buyer' => [
          'name' => $t('//ram:ApplicableHeaderTradeAgreement/ram:BuyerTradeParty/ram:Name'),
          'address' => [
              'postcode' => $t('//ram:ApplicableHeaderTradeAgreement/ram:BuyerTradeParty/ram:PostalTradeAddress/ram:PostcodeCode'),
              'line1'    => $t('//ram:ApplicableHeaderTradeAgreement/ram:BuyerTradeParty/ram:PostalTradeAddress/ram:LineOne'),
              'city'     => $t('//ram:ApplicableHeaderTradeAgreement/ram:BuyerTradeParty/ram:PostalTradeAddress/ram:CityName'),
              'country'  => $t('//ram:ApplicableHeaderTradeAgreement/ram:BuyerTradeParty/ram:PostalTradeAddress/ram:CountryID'),
          ],
      ],
      'payment' => [
          'meansTypeCode' => $t('//ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementPaymentMeans/ram:TypeCode'),
          'iban'          => $t('//ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementPaymentMeans/ram:PayeePartyCreditorFinancialAccount/ram:IBANID'),
          'bic'           => $t('//ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementPaymentMeans/ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID'),
          'termsDescription' => $t('//ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradePaymentTerms/ram:Description'),
          'dueDate'       => normalizeDate($t('//ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime/udt:DateTimeString')),
      ],
      'headerTaxes' => [],
      'totals' => [
          'lineTotal'     => moneyNode($xp, '//ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:LineTotalAmount'),
          'taxBasisTotal' => moneyNode($xp, '//ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:TaxBasisTotalAmount'),
          'taxTotal'      => moneyNode($xp, '//ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:TaxTotalAmount'),
          'grandTotal'    => moneyNode($xp, '//ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:GrandTotalAmount'),
          'duePayable'    => moneyNode($xp, '//ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:DuePayableAmount'),
      ],
      'lines' => [],
  ];
  
  foreach ($xp->query('//rsm:ExchangedDocument/ram:IncludedNote/ram:Content') as $n) {
    $res['document']['notes'][] = trim($n->textContent);
  }
  
  // Header VAT lines
  foreach ($xp->query('//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax') as $taxNode) {
    $res['headerTaxes'][] = [
        'typeCode'  => textFrom($xp, $taxNode, './ram:TypeCode'),
        'category'  => textFrom($xp, $taxNode, './ram:CategoryCode'),
        'rate'      => toFloat(textFrom($xp, $taxNode, './ram:RateApplicablePercent')),
        'basis'     => moneyFrom($xp, $taxNode, './ram:BasisAmount'),
        'amount'    => moneyFrom($xp, $taxNode, './ram:CalculatedAmount'),
    ];
  }
  
  // Line items
  foreach ($xp->query('//ram:IncludedSupplyChainTradeLineItem') as $li) {
    $line = [
        'lineId'   => textFrom($xp, $li, './ram:AssociatedDocumentLineDocument/ram:LineID'),
        'name'     => textFrom($xp, $li, './ram:SpecifiedTradeProduct/ram:Name'),
        'detail'     => textFrom($xp, $li, './ram:SpecifiedTradeProduct/ram:Description'),
        
        'quantity' => [
            'value'   => toFloat(textFrom($xp, $li, './ram:SpecifiedLineTradeDelivery/ram:BilledQuantity')),
            'unitCode'=> attrFrom($xp, $li, './ram:SpecifiedLineTradeDelivery/ram:BilledQuantity', 'unitCode'),
        ],
        
        'netUnitPrice' => moneyFrom($xp, $li, './ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:ChargeAmount'),
        
        'tax' => [
            'typeCode' => textFrom($xp, $li, './ram:SpecifiedLineTradeSettlement/ram:ApplicableTradeTax/ram:TypeCode'),
            'category' => textFrom($xp, $li, './ram:SpecifiedLineTradeSettlement/ram:ApplicableTradeTax/ram:CategoryCode'),
            'rate'     => toFloat(textFrom($xp, $li, './ram:SpecifiedLineTradeSettlement/ram:ApplicableTradeTax/ram:RateApplicablePercent')),
        ],
        
        'lineTotal' => moneyFrom($xp, $li, './ram:SpecifiedLineTradeSettlement/ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount'),
    ];
    
    $res['lines'][] = $line;
  }
  
  return $res;
}

/* ---------------- Helpers ---------------- */

function xpathText(DOMXPath $xp, string $q): string {
  $n = $xp->query($q);
  if (!$n || $n->length === 0) return '';
  return trim($n->item(0)->textContent);
}

function xpathTexts(DOMXPath $xp, string $q): array {
  $out = [];
  $nodes = $xp->query($q);
  if (!$nodes) return $out;
  foreach ($nodes as $n) $out[] = trim($n->textContent);
  return $out;
}

function xpathAttr(DOMXPath $xp, string $q, string $attr): string {
  $n = $xp->query($q);
  if (!$n || $n->length === 0) return '';
  $node = $n->item(0);
  return $node instanceof DOMElement && $node->hasAttribute($attr) ? $node->getAttribute($attr) : '';
}

function textFrom(DOMXPath $xp, DOMNode $ctx, string $q): string {
  $n = $xp->query($q, $ctx);
  if (!$n || $n->length === 0) return '';
  return trim($n->item(0)->textContent);
}

function attrFrom(DOMXPath $xp, DOMNode $ctx, string $q, string $attr): string {
  $n = $xp->query($q, $ctx);
  if (!$n || $n->length === 0) return '';
  $node = $n->item(0);
  return $node instanceof DOMElement && $node->hasAttribute($attr) ? $node->getAttribute($attr) : '';
}

function toFloat(string $s): ?float {
  $s = trim($s);
  if ($s === '') return null;
  return (float)str_replace(',', '.', $s);
}

function moneyNode(DOMXPath $xp, string $q): array {
  $n = $xp->query($q);
  if (!$n || $n->length === 0) return ['value' => null, 'currency' => null];
  $node = $n->item(0);
  $val = toFloat(trim($node->textContent));
  $cur = ($node instanceof DOMElement && $node->hasAttribute('currencyID')) ? $node->getAttribute('currencyID') : null;
  return ['value' => $val, 'currency' => $cur];
}

function moneyFrom(DOMXPath $xp, DOMNode $ctx, string $q): array {
  $n = $xp->query($q, $ctx);
  if (!$n || $n->length === 0) return ['value' => null, 'currency' => null];
  $node = $n->item(0);
  $val = toFloat(trim($node->textContent));
  $cur = ($node instanceof DOMElement && $node->hasAttribute('currencyID')) ? $node->getAttribute('currencyID') : null;
  return ['value' => $val, 'currency' => $cur];
}

function firstMatchingTaxId(DOMXPath $xp, string $q): ?string {
  $n = $xp->query($q);
  if (!$n || $n->length === 0) return null;
  $v = trim($n->item(0)->textContent);
  return $v === '' ? null : $v;
}

function normalizeDate(string $raw): ?string {
  $raw = trim($raw);
  if ($raw === '') return null;
  if (preg_match('/^\d{8}$/', $raw)) {
    return substr($raw,0,4).'-'.substr($raw,4,2).'-'.substr($raw,6,2);
  }
  if (preg_match('/^\d{4}-\d{2}-\d{2}$/', $raw)) return $raw;
  return null;
}
// ------------------------------------------------------


// ------------------------------------------------------
// create ProviderBill
// ------------------------------------------------------
function createProviderBillFromFacturX(array $data, int $idProvider): ProviderBill {
  $bill = new ProviderBill();
  
  $ref = $data['document']['id'] ?? null;
  
  $bill->reference = $ref;
  $bill->name      = $ref ;
  $bill->date      = $data['document']['issueDate'] ?: date('Y-m-d');
  
  $notes = $data['document']['notes'] ?? [];
  $bill->description = $notes ? implode("\n", $notes) : null;
  
  $bill->externalReference = $data['order']['buyerOrderRef'] ?? null;
  
  $bill->paymentCondition = $data['payment']['termsDescription'] ?? null;
  $bill->paymentDueDate   = $data['payment']['dueDate'] ?? null;
  
  $bill->idProvider = $idProvider;
  
  $idProject = Project::getSelectedProject();
  
  if (ctype_digit($idProject) && (int)$idProject > 0) {
    $bill->idProject = (int)$idProject;
  } else {
    $defaultProject = Parameter::getGlobalParameter('defaultProject');    
    if ($defaultProject) {
      $bill->idProject = (int)$defaultProject;
    } else {
      $p = new Project();
      $projects = $p->getSqlElementsFromCriteria([], false, null, 'id ASC');
      
      if (!empty($projects) && !empty($projects[0]->id)) {
        $bill->idProject = (int)$projects[0]->id;
      } else {
        $bill->idProject = 1;
      }
    }
  }

  // amount header 
  $untaxed = $data['totals']['taxBasisTotal']['value'] ?? null;
  $taxAmt  = $data['totals']['taxTotal']['value'] ?? null;
  $full    = $data['totals']['grandTotal']['value'] ?? null;
  
  $bill->untaxedAmount = $untaxed;
  $bill->taxAmount     = $taxAmt;
  $bill->fullAmount    = $full;
  
  $bill->totalUntaxedAmount = $untaxed;
  $bill->totalTaxAmount     = $taxAmt;
  $bill->totalFullAmount    = $full;
  
  if (!empty($data['headerTaxes']) && count($data['headerTaxes']) === 1) {
    $bill->taxPct = $data['headerTaxes'][0]['rate'] ?? null;
  }
  
  $bill->idUser = getCurrentUserId();
  
  //get deflaut ProviderType
  $bill->idProviderBillType = resolveDefaultProviderBillTypeId();
  $bill->idStatus           = 1;
  
  $res = $bill->save();
  if (getLastOperationStatus($res) !== 'OK') {
    throw new Exception("Save ProviderBill KO : ".$res);
  }
  
  return $bill;
}

function normalizeVat(?string $vat): ?string {
  if (!$vat) return null;
  $vat = preg_replace('/\s+/', '', trim($vat));
  return $vat ?: null;
}

// ------------------------------------------------------
// Gestion providerType
// ------------------------------------------------------

function resolveDefaultProviderBillTypeId(): int {
  
  $pbt = new Type();
  $crit=array('scope'=>'ProviderBill');
  $types = $pbt->getSqlElementsFromCriteria($crit,false,null,'id ASC');
  
  if (!empty($types) && !empty($types[0]->id)) {
    return (int)$types[0]->id;
  }
}

// ------------------------------------------------------
// Try to Find Provider if not créate im
// ------------------------------------------------------

function findOrCreateProviderFromFacturX(array $data): int {
  $sellerName = trim((string)($data['seller']['name'] ?? ''));
  $sellerVat  = normalizeVat($data['seller']['vat'] ?? null);
  
  if (!$sellerName && !$sellerVat) {
    throw new Exception(i18n("importFacturXNoSeller"));
  }
  
  //try to match by TVA
  if ($sellerVat) {
    $provider = SqlElement::getFirstSqlElementFromCriteria('Provider', ['numTax' => $sellerVat]);
    if ($provider && !empty($provider->id)) {
      return (int)$provider->id;
    }
  }
  
  //try to match by Name
  if ($sellerName) {
    $provider = SqlElement::getFirstSqlElementFromCriteria('Provider', ['name' => $sellerName]);
    if ($provider && !empty($provider->id)) {
      return (int)$provider->id;
    }
  }
  
  //else create
  $p = new Provider();
  $p->name   = $sellerName ?: ('Provider '.$sellerVat);
  $p->numTax = $sellerVat;
  
  $addr = $data['seller']['address'] ?? [];
  $p->zip     = $addr['postcode'] ?? null;
  $p->street  = $addr['line1'] ?? null;
  $p->city    = $addr['city'] ?? null;
  $p->country = $addr['country'] ?? null;
  
  $res = $p->save();
  if (getLastOperationStatus($res) !== 'OK') {
    throw new Exception("Création Provider KO : ".$res);
  }
  
  return (int)$p->id;
}

// ------------------------------------------------------
// Gestion of bill ligne
// ------------------------------------------------------

function createProviderBillLines(array $data, ProviderBill $bill): void {
  
  foreach (($data['lines'] ?? []) as $l) {
    
    $qty    = (float)($l['quantity']['value'] ?? 1);
    $pu     = isset($l['netUnitPrice']['value']) ? (float)$l['netUnitPrice']['value'] : null;
    $lineHT = isset($l['lineTotal']['value']) ? (float)$l['lineTotal']['value'] : null;
    
    if ($lineHT === null && $qty && $pu !== null) {
      $lineHT = round($qty * $pu, 2);
    }
    
    $bl = new BillLine();
    
    $bl->refType = 'ProviderBill';
    $bl->refId   = $bill->id;
    
    $bl->line        = (int)($l['lineId'] ?? 0);
    $bl->quantity    = $qty;
    $bl->price       = $pu;
    $bl->amount      = $lineHT;
    $bl->description = $l['name'] ?? null;
    $bl->detail      = $l['detail'] ?? null;
    
    // unitCode
    $unitCode = $l['quantity']['unitCode'] ?? null;
    if ($unitCode) {
      $defaultIdMeasureUnit="1";
      $missingUnits = [];
      $idMeasureUnit=1;
      $mu = new MeasureUnit();
      $idMeasureUnit = $mu::getMeasureUnitIdFromInput($unitCode, $defaultIdMeasureUnit, $missingUnits);
      $bl->idMeasureUnit = $idMeasureUnit;
    }
    
    $res = $bl->save();
    if (getLastOperationStatus($res) !== 'OK') {
      throw new Exception("Save BillLine KO : ".$res);
    }
  }
}