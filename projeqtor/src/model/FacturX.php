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

class FacturX {
  
  
  /** ==========================================================================
   * outputFromBillId
   * @param $bildId | Id of the bill
   * @return Array | All data need for XML Generate output
   */
  /** ========================================================================
   * Return a Array of Data can use for créate XML in EN16931
   */
  public static function outputFromBillId(int $billId, bool $attachMode = false) {
    
    $error="";
    //get bill
    $bill = new Bill($billId);
    if (!$bill->id) {
      echo '<div class="messageERRORFacturXNoBill" style="padding:10px; font-family: Verdana, Arial, Tahoma, sans-serif;">';
      echo '<h3>'.i18n("facturXMessageErrorNoBill").':</h3>';
      echo '</div>';
      $errorMessage = html_entity_decode(i18n("facturXMessageErrorNoBill"), ENT_QUOTES | ENT_HTML5, 'UTF-8');
      if(!$attachMode){
        exit;
      }else{
        return($errorMessage);
      }
    }
    //get client
    $client = new Client($bill->idClient);
    
    //get sellers
    $sellers = new Recipient($bill->idRecipient);
    
    //get all bill lines
    $BillLine = new BillLine();
    //$linesList = $BillLine->getSqlElementsFromCriteria(['refId' => $billId]);
    $linesList = $BillLine->getSqlElementsFromCriteria(['refId' => $billId,'refType'=>get_class($bill)]);
    
    if (empty($linesList)) {
      echo '<div class="messageERRORFacturXBillLine" style="padding:10px; font-family: Verdana, Arial, Tahoma, sans-serif;">';
      echo '<h3>'.i18n("facturXMessageErrorBillLine").':</h3>';
      echo '</div>';
      $errorMessage = html_entity_decode(i18n("facturXMessageErrorBillLine"), ENT_QUOTES | ENT_HTML5, 'UTF-8');
      if(!$attachMode){
        exit;
      }else{
        return($errorMessage);
      }
    }

    //seller data
    $seller = [
        'name' => $sellers->designation??$sellers->name,
        'siret' => $sellers->companyNumber,
        'vat' => $sellers->numTax,
        'addr1' => $sellers->street,
        'addr2' => $sellers->complement ?: '',
        'zip' => $sellers->zip,
        'city' => $sellers->city,
        'country' =>self::countryToIso2($sellers->country),
    ];
    
    //paymentDeadline
    $termsDesc = '';
    if (!empty($bill->idPaymentDelay)) {
      $pd = new PaymentDelay($bill->idPaymentDelay);
      $termsDesc = $pd->name;
    }
    $payment = [
        'meansCode' => '58',
        'iban' => $sellers->bankInternationalAccountNumber,
        'bic' => $sellers->bankIdentificationCode ?: '',
        'termsDesc' =>$termsDesc ?: '',
        'dueDate' => $bill->paymentDueDate,
    ];
    
    // build Bill line
    $xmlLines = [];
    $taxesByRate = [];
    
    foreach ($linesList as $bl) {
      $qty = (float)$bl->quantity;
      $unitPrice = (float)$bl->price;
      $vatRate=(float)$bill->taxPct??(float)$client->taxPct;
      $lineTotal = round($qty * $unitPrice, 2);
      
      $unitCode = 'C62';
      
      if (!empty($bl->idMeasureUnit)) {
        $uObj = new MeasureUnit($bl->idMeasureUnit);
        $unitCode = self::resolveRec20UnitFromName($uObj->name ?? '');
      }
      
      $xmlLines[] = [
          'name' => $bl->description,
          'detail' => $bl->detail ?? '',
          'qty' => $qty,
          'unitCode' => $unitCode,
          'unitPrice' => $unitPrice,
          'lineTotal' => $lineTotal,
          'vatRate' => $vatRate,
          'vatCategory' => 'S',
      ];
      
      $key = (string)$vatRate;
      if (!isset($taxesByRate[$key])) {
        $taxesByRate[$key] = [
            'rate' => $vatRate,
            'basis' => 0,
            'vat' => 0,
            'category' => 'S'
        ];
      }
      $taxesByRate[$key]['basis'] += $lineTotal;
      $taxesByRate[$key]['vat'] += round($lineTotal * $vatRate / 100, 2);
    }
    
    // build the data for the generate
    $data = [
        'invoice' => [
            'number' => $bill->name,
            'date' => $bill->date,
            'currency' => 'EUR',
            'typeCode' => '380',
            'orderRef' => $bill->reference ?? '',
            'note' =>  htmlEncode($bill->description,'htmlNoNl2br'),
            'sendDate' => $bill->sendDate,
        ],
        'seller' => $seller,
        'buyer' => [
            'name' => $client->designation??$client->name,
            'addr1' => $client->street,
            'addr2' => $client->complement ?: '',
            'zip' => $client->zip,
            'city' => $client->city,
            'country' =>self::countryToIso2($client->country),
        ],
        'lines' => $xmlLines,
        'taxes' => array_values($taxesByRate),
        'totals' => [
            'ht' => (float)$bill->untaxedAmount,
            'vat' => (float)$bill->taxAmount,
            'ttc' => (float)$bill->fullAmount,
        ],
        'payment' => $payment,
    ];
    
    //check data null before
    $tax = array();
    $taxCheck = false;
    $missing = self::findEmptyValues($data,$tax);
    $taxVat = $tax['vat'];
    $taxVatRate = $tax['vatRate'];
    $taxHt = $tax['ht'];
    $taxTtc = $tax['ttc'];
    if( ($taxHt*$taxVatRate/100) == $taxVat ){
      $taxCheck = true;
    }
    if( ($taxHt+$taxVat) == $taxTtc){
      $taxCheck = true;
    }
    if (!empty($missing)) {
      $errorMessage = html_entity_decode(i18n("facturXMessageError"), ENT_QUOTES | ENT_HTML5, 'UTF-8')
      . " :<br><br> - "
          . implode("<br> - ", array_map('htmlEncode', $missing));
      
      if (!$attachMode) {
        echo '<div class="messageERRORFacturX" style="padding:10px; font-family: Verdana, Arial, Tahoma, sans-serif;">';
        echo '<h3>' . i18n("facturXMessageError") . ':</h3>';
        echo '<ul style="margin:8px 0 0 18px; list-style-type: circle;">';
        foreach ($missing as $field) {
          echo '<li>' . htmlEncode($field) . '</li>';
        }
        echo '</ul>';
        echo '</div>';
        exit;
      } else {
        return $errorMessage;
      }
    }else if(!$taxCheck){
      echo '<div class="messageERRORFacturX" style="padding:10px; font-family: Verdana, Arial, Tahoma, sans-serif;">';
      echo '<h3>'.i18n("facturXMessageErrorTax").':</h3>';
      echo '</div>';
      $errorMessage = html_entity_decode(i18n("facturXMessageErrorTax"), ENT_QUOTES | ENT_HTML5, 'UTF-8');
      if(!$attachMode){
        exit;
      }else{
        return($errorMessage);
      }
    }else{
      //generate
      self::output($data);
    }
  }
  
  /** ==========================================================================
   * output
   * @param $data | Array of all Data need for generate
   * @return xml print
   */
  /** ========================================================================
   * Return a print of bill in XML with standard EN16931
   */
  public static function output(array $data) {
    
    $nl  = "\n";
    $tab = "  ";
    
    $invoiceNumber = $data['invoice']['number'] ?? '';
    $docTypeCode   = $data['invoice']['typeCode'] ?? '380'; // 380=invoice, 381=credit note
    $currency      = $data['invoice']['currency'] ?? 'EUR';
    
    $invoiceDate   = self::yyyymmdd($data['invoice']['date'] ?? '');
    $note          = $data['invoice']['note'];
    
    $seller = $data['seller'] ?? [];
    $buyer  = $data['buyer'] ?? [];
    $payment = $data['payment'] ?? [];
    $totals = $data['totals'] ?? [];
    $lines  = $data['lines'] ?? [];
    $taxes  = $data['taxes'] ?? [];
    
    $dueDate = self::yyyymmdd($payment['dueDate'] ?? ($data['invoice']['date'] ?? ''));
    $sendDate = $data['invoice']['sendDate']??'';
    $deliveryDate="";
    if($sendDate)$deliveryDate = self::yyyymmdd($data['invoice']['sendDate']);
    
    
    $guideline = 'urn:cen.eu:en16931:2017';//guideLine for context in XML (L209~)
    
    echo '<?xml version="1.0" encoding="UTF-8"?>' . $nl;
    echo '<rsm:CrossIndustryInvoice'
        . ' xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"'
            . ' xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"'
                . ' xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"'
                    . ' xmlns:qdt="urn:un:unece:uncefact:data:standard:QualifiedDataType:100"'
                        . '>' . $nl;
                        
                        // Context
                        echo $tab . '<rsm:ExchangedDocumentContext>' . $nl;
                        echo $tab.$tab . '<ram:GuidelineSpecifiedDocumentContextParameter>' . $nl;
                        echo $tab.$tab.$tab . '<ram:ID>' . self::xmlClean($guideline) . '</ram:ID>' . $nl;
                        echo $tab.$tab . '</ram:GuidelineSpecifiedDocumentContextParameter>' . $nl;
                        echo $tab . '</rsm:ExchangedDocumentContext>' . $nl;
                        
                        // Document
                        echo $tab . '<rsm:ExchangedDocument>' . $nl;
                        echo $tab.$tab . '<ram:ID>' . self::xmlClean($invoiceNumber) . '</ram:ID>' . $nl;
                        echo $tab.$tab . '<ram:TypeCode>' . self::xmlClean($docTypeCode) . '</ram:TypeCode>' . $nl;
                        echo $tab.$tab . '<ram:IssueDateTime>' . $nl;
                        echo $tab.$tab.$tab . '<udt:DateTimeString format="102">' . self::xmlClean($invoiceDate) . '</udt:DateTimeString>' . $nl;
                        echo $tab.$tab . '</ram:IssueDateTime>' . $nl;
                        
                        if (trim((string)$note) !== '') {
                          echo $tab.$tab . '<ram:IncludedNote>' . $nl;
                          echo $tab.$tab.$tab . '<ram:Content>' . self::xmlClean($note) . '</ram:Content>' . $nl;
                          echo $tab.$tab . '</ram:IncludedNote>' . $nl;
                        }
                        
                        echo $tab . '</rsm:ExchangedDocument>' . $nl;
                        
                        // Transaction
                        echo $tab . '<rsm:SupplyChainTradeTransaction>' . $nl;
                        
                        // Lines
                        $lineNo = 1;
                        foreach ($lines as $l) {
                          self::echoLine($l, $lineNo, $currency, $tab, $nl);
                          $lineNo++;
                        }
                        
                        // Header Agreement
                        echo $tab.$tab . '<ram:ApplicableHeaderTradeAgreement>' . $nl;
                        
                        // SellerTradeParty
                        echo $tab.$tab.$tab . '<ram:SellerTradeParty>' . $nl;
                        echo $tab.$tab.$tab.$tab . '<ram:Name>' . self::xmlClean($seller['name'] ?? '') . '</ram:Name>' . $nl;
                        
                        // Legal org
                        echo $tab.$tab.$tab.$tab . '<ram:SpecifiedLegalOrganization>' . $nl;
                        echo $tab.$tab.$tab.$tab.$tab . '<ram:ID>' . self::xmlClean($seller['siret'] ?? '') . '</ram:ID>' . $nl;
                        echo $tab.$tab.$tab.$tab . '</ram:SpecifiedLegalOrganization>' . $nl;
                        
                        // Address
                        echo $tab.$tab.$tab.$tab . '<ram:PostalTradeAddress>' . $nl;
                        echo $tab.$tab.$tab.$tab.$tab . '<ram:PostcodeCode>' . self::xmlClean($seller['zip'] ?? '') . '</ram:PostcodeCode>' . $nl;
                        echo $tab.$tab.$tab.$tab.$tab . '<ram:LineOne>' . self::xmlClean($seller['addr1'] ?? '') . '</ram:LineOne>' . $nl;
                        echo $tab.$tab.$tab.$tab.$tab . '<ram:CityName>' . self::xmlClean($seller['city'] ?? '') . '</ram:CityName>' . $nl;
                        echo $tab.$tab.$tab.$tab.$tab . '<ram:CountryID>' . self::xmlClean($seller['country']) . '</ram:CountryID>' . $nl;
                        echo $tab.$tab.$tab.$tab . '</ram:PostalTradeAddress>' . $nl;
                        
                        // VAT registration
                        echo $tab.$tab.$tab.$tab . '<ram:SpecifiedTaxRegistration>' . $nl;
                        echo $tab.$tab.$tab.$tab.$tab . '<ram:ID>' . self::xmlClean($seller['vat'] ?? '') . '</ram:ID>' . $nl;
                        echo $tab.$tab.$tab.$tab . '</ram:SpecifiedTaxRegistration>' . $nl;
                        echo $tab.$tab.$tab.$tab . '<ram:SpecifiedTaxRegistration>' . $nl;
                        echo $tab.$tab.$tab.$tab.$tab . '<ram:ID schemeID="VA">' . self::xmlClean($seller['vat']) . '</ram:ID>' . $nl;
                        echo $tab.$tab.$tab.$tab . '</ram:SpecifiedTaxRegistration>' . $nl;
                        echo $tab.$tab.$tab . '</ram:SellerTradeParty>' . $nl;
                        
                        // BuyerTradeParty
                        echo $tab.$tab.$tab . '<ram:BuyerTradeParty>' . $nl;
                        echo $tab.$tab.$tab.$tab . '<ram:Name>' . self::xmlClean($buyer['name'] ?? '') . '</ram:Name>' . $nl;
                        
                        echo $tab.$tab.$tab.$tab . '<ram:PostalTradeAddress>' . $nl;
                        echo $tab.$tab.$tab.$tab.$tab . '<ram:PostcodeCode>' . self::xmlClean($buyer['zip'] ?? '') . '</ram:PostcodeCode>' . $nl;
                        echo $tab.$tab.$tab.$tab.$tab . '<ram:LineOne>' . self::xmlClean($buyer['addr1'] ?? '') . '</ram:LineOne>' . $nl;
                        
                        if (!empty($buyer['addr2'])) {
                          echo $tab.$tab.$tab.$tab.$tab . '<ram:LineTwo>' . self::xmlClean($buyer['addr2']) . '</ram:LineTwo>' . $nl;
                        }
                        
                        echo $tab.$tab.$tab.$tab.$tab . '<ram:CityName>' . self::xmlClean($buyer['city'] ?? '') . '</ram:CityName>' . $nl;
                        echo $tab.$tab.$tab.$tab.$tab . '<ram:CountryID>' . self::xmlClean($buyer['country']) . '</ram:CountryID>' . $nl;
                        echo $tab.$tab.$tab.$tab . '</ram:PostalTradeAddress>' . $nl;
                        echo $tab.$tab.$tab . '</ram:BuyerTradeParty>' . $nl;
                        
                        // Buyer order reference
                        if (!empty($data['invoice']['orderRef'])) {
                          echo $tab.$tab.$tab . '<ram:BuyerOrderReferencedDocument>' . $nl;
                          echo $tab.$tab.$tab.$tab . '<ram:IssuerAssignedID>' . self::xmlClean($data['invoice']['orderRef']) . '</ram:IssuerAssignedID>' . $nl;
                          echo $tab.$tab.$tab . '</ram:BuyerOrderReferencedDocument>' . $nl;
                        }
                        
                        echo $tab.$tab . '</ram:ApplicableHeaderTradeAgreement>' . $nl;
                        
                        // Delivery
                        echo $tab.$tab . '<ram:ApplicableHeaderTradeDelivery>' . $nl;
                        echo $tab.$tab.$tab . '<ram:ActualDeliverySupplyChainEvent>' . $nl;
                        echo $tab.$tab.$tab.$tab . '<ram:OccurrenceDateTime>' . $nl;
                        echo $tab.$tab.$tab.$tab.$tab. '<udt:DateTimeString format="102">'. self::xmlClean($deliveryDate). '</udt:DateTimeString>' . $nl;
                        echo $tab.$tab.$tab.$tab . '</ram:OccurrenceDateTime>' . $nl;
                        echo $tab.$tab.$tab . '</ram:ActualDeliverySupplyChainEvent>' . $nl;
                        echo $tab.$tab . '</ram:ApplicableHeaderTradeDelivery>' . $nl;
                        
                        // Settlement
                        echo $tab.$tab . '<ram:ApplicableHeaderTradeSettlement>' . $nl;
                        echo $tab.$tab.$tab . '<ram:InvoiceCurrencyCode>' . self::xmlClean($currency) . '</ram:InvoiceCurrencyCode>' . $nl;
                        
                        // Payment means
                        echo $tab.$tab.$tab . '<ram:SpecifiedTradeSettlementPaymentMeans>' . $nl;
                        echo $tab.$tab.$tab.$tab . '<ram:TypeCode>' . self::xmlClean($payment['meansCode'] ?? '58') . '</ram:TypeCode>' . $nl;
                        
                        echo $tab.$tab.$tab.$tab . '<ram:PayeePartyCreditorFinancialAccount>' . $nl;
                        echo $tab.$tab.$tab.$tab.$tab . '<ram:IBANID>' . self::xmlClean($payment['iban'] ?? '') . '</ram:IBANID>' . $nl;
                        echo $tab.$tab.$tab.$tab . '</ram:PayeePartyCreditorFinancialAccount>' . $nl;
                        
                        echo $tab.$tab.$tab.$tab . '<ram:PayeeSpecifiedCreditorFinancialInstitution>' . $nl;
                        echo $tab.$tab.$tab.$tab.$tab . '<ram:BICID>' . self::xmlClean($payment['bic']) . '</ram:BICID>' . $nl;
                        echo $tab.$tab.$tab.$tab . '</ram:PayeeSpecifiedCreditorFinancialInstitution>' . $nl;
                        
                        echo $tab.$tab.$tab . '</ram:SpecifiedTradeSettlementPaymentMeans>' . $nl;
                        
                        // Taxes breakdown
                        foreach ($taxes as $t) {
                          self::echoTax($t, $currency, $tab, $nl);
                        }
                        
                        // Payment terms
                        echo $tab.$tab.$tab . '<ram:SpecifiedTradePaymentTerms>' . $nl;
                        echo $tab.$tab.$tab.$tab . '<ram:Description>' . self::xmlClean($payment['termsDesc'] ?? '') . '</ram:Description>' . $nl;
                        echo $tab.$tab.$tab.$tab . '<ram:DueDateDateTime>' . $nl;
                        echo $tab.$tab.$tab.$tab.$tab . '<udt:DateTimeString format="102">' . self::xmlClean($dueDate) . '</udt:DateTimeString>' . $nl;
                        echo $tab.$tab.$tab.$tab . '</ram:DueDateDateTime>' . $nl;
                        echo $tab.$tab.$tab . '</ram:SpecifiedTradePaymentTerms>' . $nl;
                        
                        // Monetary summation
                        echo $tab.$tab.$tab . '<ram:SpecifiedTradeSettlementHeaderMonetarySummation>' . $nl;
                        echo $tab.$tab.$tab.$tab . '<ram:LineTotalAmount currencyID="' . self::xmlClean($currency) . '">' . self::money($totals['ht'] ?? 0) . '</ram:LineTotalAmount>' . $nl;
                        echo $tab.$tab.$tab.$tab . '<ram:TaxBasisTotalAmount currencyID="' . self::xmlClean($currency) . '">' . self::money($totals['ht'] ?? 0) . '</ram:TaxBasisTotalAmount>' . $nl;
                        echo $tab.$tab.$tab.$tab . '<ram:TaxTotalAmount currencyID="' . self::xmlClean($currency) . '">' . self::money($totals['vat'] ?? 0) . '</ram:TaxTotalAmount>' . $nl;
                        echo $tab.$tab.$tab.$tab . '<ram:GrandTotalAmount currencyID="' . self::xmlClean($currency) . '">' . self::money($totals['ttc'] ?? 0) . '</ram:GrandTotalAmount>' . $nl;
                        echo $tab.$tab.$tab.$tab . '<ram:DuePayableAmount currencyID="' . self::xmlClean($currency) . '">' . self::money($totals['ttc'] ?? 0) . '</ram:DuePayableAmount>' . $nl;
                        echo $tab.$tab.$tab . '</ram:SpecifiedTradeSettlementHeaderMonetarySummation>' . $nl;
                        
                        echo $tab.$tab . '</ram:ApplicableHeaderTradeSettlement>' . $nl;
                        
                        // End transaction + root
                        echo $tab . '</rsm:SupplyChainTradeTransaction>' . $nl;
                        echo '</rsm:CrossIndustryInvoice>' . $nl;
  }
  
  
  private static function resolveRec20UnitFromName(?string $name): string {

    if (!$name) return 'C62';
    
    $unitCode = trim(mb_strtolower($name));
    $unitCode = iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $unitCode);
    $unitCode = preg_replace('/[^a-z0-9]/', '', $unitCode);
    
    if (preg_match('/^(piece|pieces|unit|units|item|items|pc|pcs|stk|stuck|einheit)$/', $unitCode)) {
      return 'H87';
    }
    if (preg_match('/^(lot|lots|set|sets|pack|packs|bundle|bundles|paquet|paquets)$/', $unitCode)) {
      return 'SET';
    }
    if (preg_match('/^(day|days|jour|jours|tag|tage|dia|dias)$/', $unitCode)) {
      return 'DAY';
    }
    if (preg_match('/^(month|months|mois|monat|monate|mese|mesi|mes)$/', $unitCode)) {
      return 'MON';
    }
    if (preg_match('/^(hour|hours|heure|heures|std|ora|ore)$/', $unitCode)) {
      return 'HUR';
    }
    if (preg_match('/^(year|years|annee|annees|jahr|jahre|anno|anni)$/', $unitCode)) {
      return 'ANN';
    }
    if (preg_match('/^(m|meter|metre|meters|metres)$/', $unitCode)) {
      return 'MTR';
    }
    if (preg_match('/^(m2|squaremeter|sqm)$/', $unitCode)) {
      return 'MTK';
    }
    if (preg_match('/^(m3|cubicmeter)$/', $unitCode)) {
      return 'MTQ';
    }
    if (preg_match('/^(kg|kilo|kilogram|kilograms)$/', $unitCode)) {
      return 'KGM';
    }
    if (preg_match('/^(l|liter|litre|liters|litres)$/', $unitCode)) {
      return 'LTR';
    }
    
    return 'C62';
  }
  
  
  private static function echoLine(array $l, int $lineId, string $currency, string $tab, string $nl) {
    
    $name = $l['name'] ?? '';
    $detail = $l['detail'] ?? '';
    $qty = $l['qty'] ?? 1;
    $unitCode = $l['unitCode'] ?? 'C62';
    $unitPrice = $l['unitPrice'] ?? 0;
    $lineTotal = $l['lineTotal'] ?? 0;
    $vatRate = $l['vatRate'] ?? 20;
    $vatCat = $l['vatCategory'] ?? 'S';
    
    echo $tab.$tab . '<ram:IncludedSupplyChainTradeLineItem>' . $nl;
    
    echo $tab.$tab.$tab . '<ram:AssociatedDocumentLineDocument>' . $nl;
    echo $tab.$tab.$tab.$tab . '<ram:LineID>' . self::xmlClean((string)$lineId) . '</ram:LineID>' . $nl;
    echo $tab.$tab.$tab . '</ram:AssociatedDocumentLineDocument>' . $nl;
    
    echo $tab.$tab.$tab . '<ram:SpecifiedTradeProduct>' . $nl;
    echo $tab.$tab.$tab.$tab . '<ram:Name>' . self::xmlClean($name) . '</ram:Name>' . $nl;
    echo $tab.$tab.$tab.$tab . '<ram:Description>' . self::xmlClean($detail) . '</ram:Description>' . $nl;
    
    echo $tab.$tab.$tab . '</ram:SpecifiedTradeProduct>' . $nl;
    
    echo $tab.$tab.$tab . '<ram:SpecifiedLineTradeAgreement>' . $nl;
    echo $tab.$tab.$tab.$tab . '<ram:NetPriceProductTradePrice>' . $nl;
    echo $tab.$tab.$tab.$tab.$tab . '<ram:ChargeAmount currencyID="' . self::xmlClean($currency) . '">' . self::money($unitPrice) . '</ram:ChargeAmount>' . $nl;
    echo $tab.$tab.$tab.$tab . '</ram:NetPriceProductTradePrice>' . $nl;
    echo $tab.$tab.$tab . '</ram:SpecifiedLineTradeAgreement>' . $nl;
    
    echo $tab.$tab.$tab . '<ram:SpecifiedLineTradeDelivery>' . $nl;
    echo $tab.$tab.$tab.$tab . '<ram:BilledQuantity unitCode="' . self::xmlClean($unitCode) . '">' . self::qty($qty) . '</ram:BilledQuantity>' . $nl;
    echo $tab.$tab.$tab . '</ram:SpecifiedLineTradeDelivery>' . $nl;
    
    echo $tab.$tab.$tab . '<ram:SpecifiedLineTradeSettlement>' . $nl;
    echo $tab.$tab.$tab.$tab . '<ram:ApplicableTradeTax>' . $nl;
    echo $tab.$tab.$tab.$tab.$tab . '<ram:TypeCode>VAT</ram:TypeCode>' . $nl;
    echo $tab.$tab.$tab.$tab.$tab . '<ram:CategoryCode>' . self::xmlClean($vatCat) . '</ram:CategoryCode>' . $nl;
    echo $tab.$tab.$tab.$tab.$tab . '<ram:RateApplicablePercent>' . self::xmlClean(self::rate($vatRate)) . '</ram:RateApplicablePercent>' . $nl;
    echo $tab.$tab.$tab.$tab . '</ram:ApplicableTradeTax>' . $nl;
    
    echo $tab.$tab.$tab.$tab . '<ram:SpecifiedTradeSettlementLineMonetarySummation>' . $nl;
    echo $tab.$tab.$tab.$tab.$tab . '<ram:LineTotalAmount currencyID="' . self::xmlClean($currency) . '">' . self::money($lineTotal) . '</ram:LineTotalAmount>' . $nl;
    echo $tab.$tab.$tab.$tab . '</ram:SpecifiedTradeSettlementLineMonetarySummation>' . $nl;
    echo $tab.$tab.$tab . '</ram:SpecifiedLineTradeSettlement>' . $nl;
    
    echo $tab.$tab . '</ram:IncludedSupplyChainTradeLineItem>' . $nl;
  }
  
  private static function echoTax(array $t, string $currency, string $tab, string $nl) {
    $basis = $t['basis'] ?? 0;
    $vat = $t['vat'] ?? 0;
    $rate = $t['rate'] ?? 0;
    $cat = $t['category'] ?? 'S';
    
    echo $tab.$tab.$tab . '<ram:ApplicableTradeTax>' . $nl;
    echo $tab.$tab.$tab.$tab . '<ram:CalculatedAmount currencyID="' . self::xmlClean($currency) . '">' . self::money($vat) . '</ram:CalculatedAmount>' . $nl;
    echo $tab.$tab.$tab.$tab . '<ram:TypeCode>VAT</ram:TypeCode>' . $nl;
    echo $tab.$tab.$tab.$tab . '<ram:BasisAmount currencyID="' . self::xmlClean($currency) . '">' . self::money($basis) . '</ram:BasisAmount>' . $nl;
    echo $tab.$tab.$tab.$tab . '<ram:CategoryCode>' . self::xmlClean($cat) . '</ram:CategoryCode>' . $nl;
    echo $tab.$tab.$tab.$tab . '<ram:RateApplicablePercent>' . self::xmlClean(self::rate($rate)) . '</ram:RateApplicablePercent>' . $nl;
    echo $tab.$tab.$tab . '</ram:ApplicableTradeTax>' . $nl;
  }
  
  private static function yyyymmdd($date) {
    $d = trim((string)$date);
    if (preg_match('/^\d{8}$/', $d)) return $d;
    return str_replace('-', '', $d);
  }
  
  private static function money($v) {
    return number_format((float)$v, 2, '.', '');
  }
  
  private static function rate($v) {
    return rtrim(rtrim(number_format((float)$v, 2, '.', ''), '0'), '.');
  }
  
  private static function qty($v) {
    $s = number_format((float)$v, 2, '.', '');
    $s = rtrim($s, '0');
    $s = rtrim($s, '.');
    return $s;
  }
  
  //clean correctely field for XML
  private static function xmlClean($s) {
    $s = (string)$s;
    $s = strip_tags($s);
    $s = html_entity_decode($s, ENT_QUOTES | ENT_HTML5, 'UTF-8');
    $s = str_replace("\xC2\xA0", ' ', $s); // nbsp unicode
    return htmlspecialchars($s, ENT_XML1 | ENT_QUOTES, 'UTF-8');
  }
  
  //covert contry name to ISO2 for 
  private static function countryToIso2($country){
    if (!$country) return;
    
    $map = [
        'FRANCE' => 'FR',
        'FRANCE METROPOLITAINE' => 'FR',
        'FR' => 'FR',
        
        'BELGIQUE' => 'BE',
        'BELGIUM' => 'BE',
        'BE' => 'BE',
        
        'SUISSE' => 'CH',
        'SWITZERLAND' => 'CH',
        'CH' => 'CH',
        
        'ALLEMAGNE' => 'DE',
        'GERMANY' => 'DE',
        'DE' => 'DE',
        
        'ESPAGNE' => 'ES',
        'SPAIN' => 'ES',
        'ES' => 'ES',
        
        'ITALIE' => 'IT',
        'ITALY' => 'IT',
        'IT' => 'IT',
        
        'LUXEMBOURG' => 'LU',
        'LU' => 'LU',
    ];
    
    $key = strtoupper(trim($country));
    return $map[$key] ?? 'FR';
  }
  
  //check if data no null 
  private static function findEmptyValues(array $data, &$tax, string $path = ''): array {
    $errors = [];
    foreach ($data as $key => $value) {
      $currentPath = $path === '' ? $key : $path . '.' . $key;
      if (is_array($value)) {
        $errors = array_merge(
            $errors,
            self::findEmptyValues($value, $tax, $currentPath)
            );
        //get tax field and value
        if(isset($value['vatRate']) != null){
          $tax['vatRate'] = $value['vatRate'];
        }
        if(isset($value["vat"]) != null){
          $tax["vat"] = $value['vat'];
        }
        if(isset($value["ht"]) != null){
          $tax['ht'] = $value['ht'];
        }
        if(isset($value["ttc"]) != null){
          $tax['ttc'] = $value['ttc'];
        }
      } else {
        // data incorrect
        if (($value === null || $value === '') && $key!="addr2" && $key!="note") {
          $pathError = explode('.',$currentPath);
          $pathErrorObj = $pathError[0];
          $pathErrorField = $pathError[1];
          if(isset($pathError[2])){
            $LinesErrorField = $pathError[2];
            if($LinesErrorField == "name"){
              $LinesErrorField = "description";
            }
          }
          $errorObj=ucfirst($pathErrorObj);
          //case spe for obj
          if($errorObj == "Lines")$errorObj="sectionBillLine";
          if($errorObj == "Buyer" )$errorObj="Client";
          if($errorObj == "Seller" )$errorObj="Recipient";
          if($errorObj == "Payment" ){
            if($pathErrorField == "iban")$errorObj="Recipient";
            if($pathErrorField == "bic")$errorObj="Recipient";
            if($pathErrorField == "termsDesc")$errorObj="Invoice";
            if($pathErrorField == "dueDate")$errorObj="Invoice";
          }
          $errorfield="col".ucfirst($pathErrorField);  
          if(isset($LinesErrorField)){
            $errorfield="col".ucfirst($LinesErrorField);
          }
          //case spe for field
          if( $key == "bic" )$errorfield="colBankIdentificationCode";
          if( $key == "addr1" )$errorfield="colStreet";
          if( $key == "iban" )$errorfield="colBankInternationalAccountNumber";
          if( $key == "siret" )$errorfield="colCompanyNumber";
          if( $key == "termsDesc" )$errorfield="colPaymentDueDate";
          if( $key == "orderRef" )$errorfield="colBillReference";
          if( $key == "vat" )$errorfield="colNumTax";
          
          $errors[]= i18n($errorObj)." => ".i18n($errorfield);
        }
      }
    }
    return $errors;
  }

}