<?php
use Spipu\Html2Pdf\Html2Pdf;
use Mpdf\Mpdf;
use PhpOffice\PhpSpreadsheet\Spreadsheet;
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

/* ============================================================================
 * Print page of application.
 */
/* Possible outMode
 *  - html     : printing of detail or list or report (it is default value)
 *  - pdf      : pdf printing
 *  - csv      : CSV export of list
 *  - mpp      : export of planning to project xml format
 *  - word     : export to word (TBS)
 *  - excel    : export to excel (TBS)
 *  - download : direct download, whatever the file
 *  - downloadPdf : transform to pdf (like "pdf") and direct download file
 */
   require_once "../tool/projeqtor.php";
   
   scriptLog('   ->/view/print.php'); 
   projeqtor_set_time_limit(300);
   ob_start();
   
   $outMode='html';
   $pdfLib='html2pdf';
   if (isWkHtmlEnabled()) {
     $pdfLib='WkHtmlToPdf';
   }
   
   $printInNewPage=getPrintInNewWindow();
   if (pq_array_key_exists('outMode', $_REQUEST)) {
     if ($_REQUEST['outMode']) {
       $outMode=$_REQUEST['outMode'];
     }
   }
   $orientation='L';
   if (pq_array_key_exists('orientation', $_REQUEST)) {
   	$orientation=$_REQUEST['orientation'];
   }
   $attach=false;
   if (pq_array_key_exists('attach', $_REQUEST)) {
     if ($_REQUEST['attach']) {
       $attach=$_REQUEST['attach'];
     }
   }
   //gestion of facturX
   if($outMode=="pdf" && Parameter::getGlobalParameter("ExportBillInFormatFacturX")=="YES" && RequestHandler::getClass("objectClass")=="Bill"){
     $facturxMode = true;
   } else {
     $facturxMode = false;
   }

   
   $download=(RequestHandler::getValue('context')=='download' or RequestHandler::getValue('context')=='downloadList')?true:false; // Attention, download without extend is not like other download outmode
   $noHeader=(RequestHandler::getValue('context')=='noheader' or RequestHandler::getValue('context')=='noheaderList')?true:false;
   if ($outMode=='downloadPdf') $outMode='pdf';
   if ($outMode=='pdf') {
     $printInNewPage=getPrintInNewWindow('pdf');
     $memoryLimitForPDF=Parameter::getGlobalParameter('paramMemoryLimitForPDF');
     if (isset($memoryLimitForPDF)) {
       $limit=$memoryLimitForPDF;	
     } else {
     	 $limit='';
     }
     if ($limit===0) {
     	 header ('Content-Type: text/html; charset=UTF-8');
     	 echo "<html><head></head><body>";
     	 echo i18n("msgPdfDisabled");
     	 echo "</body></html>";
     	 return;
     } else if ($limit=='') {
       // Keep existing
     } else {
      projeqtor_set_memory_limit($limit.'M');
     }
   } 
   if ($outMode=='csv')  {
     $contentType="application/force-download";
     $nameReport=RequestHandler::getValue('reportCodeName');
     if ($nameReport) $nameReport=base64_decode($nameReport);
     $objectClass=RequestHandler::getValue('objectClass');
     $name="export_" . (($nameReport)?$nameReport:$objectClass) . "_" . date('Ymd_His') . ".csv";
     header("Content-Type: " . $contentType . "; name=\"" . $name . "\""); 
	   header("Content-Transfer-Encoding: binary"); 
	   //header("Content-Length: $size"); 
	   header("Content-Disposition: attachment; filename=\"" .$name . "\""); 
	   header("Expires: 0"); 
	   header("Cache-Control: no-cache, must-revalidate");
	   header("Pragma: no-cache");
   } else if ($outMode=='mpp')  {
     $contentType="application/force-download";
     $name="export_planning_" . date('Ymd_His') . ".xml";
     header("Content-Type: " . $contentType . "; name=\"" . $name . "\""); 
     header("Content-Transfer-Encoding: binary"); 
     //header("Content-Length: $size"); 
     header("Content-Disposition: attachment; filename=\"" .$name . "\""); 
     header("Expires: 0"); 
     header("Cache-Control: no-cache, must-revalidate");
     header("Pragma: no-cache");
   } else if ($outMode=='word' or $outMode=='excel' or $outMode == "download")  {
     
   } else if ($download)  { // all downloadXxx except download
     $printInNewPage=true;
     $contentType="application/force-download";
     $nameReport=RequestHandler::getValue('reportCodeName');
     if ($nameReport) $nameReport=base64_decode($nameReport);
     $objectClass=RequestHandler::getValue('objectClass');
     $objectId=RequestHandler::getValue('objectId');
     $ext=pq_strtolower(pq_str_replace('download','',$outMode));
     if ($objectClass) {
       if ($objectId) {
         $name=i18n($objectClass).'_'.intval($objectId);
       } else {
         $name=i18n('menu'.$objectClass);
       }
     } else {
       $name="export";
     }
     $name.="_".date('Ymd_His').'.'.$ext;
     $idTemplate=RequestHandler::getId('idTemplate');
     if (!$idTemplate and pq_strpos(RequestHandler::getValue('page'), 'idTemplate=')) {
       $split=pq_explode('?',RequestHandler::getValue('page'));
       if (count($split)>1) {
         $spl=pq_explode('&',$split[1]);
         foreach($spl as $sp) {
           $rsp=pq_explode('=', $sp);
           if (count($rsp)==2 and $rsp[0]=='idTemplate') {
             $idTemplate=$rsp[1];
           }
         }
       }
     }
     if ($idTemplate) {
       $noHeader=true;
       $objectClass=RequestHandler::getClass('objectClass');
       $className=i18n($objectClass);
       $id=RequestHandler::getId('objectId');
       $obj=null;
       if ($objectClass) $obj=new $objectClass($id);
       $tmp=new TemplateReport($idTemplate);
       $tmpName=(method_exists($tmp, 'getOutputFileName'))?$tmp->getOutputFileName($obj):null;
       if ($tmpName) $name=$tmpName;
     }
     header("Content-Type: " . $contentType . "; name=\"" . $name . "\""); 
	   header("Content-Transfer-Encoding: binary"); 
	   //header("Content-Length: $size"); 
	   header("Content-Disposition: attachment; filename=\"" .$name . "\""); 
	   header("Expires: 0"); 
	   header("Cache-Control: no-cache, must-revalidate");
	   header("Pragma: no-cache");
   } else {
     header ('Content-Type: text/html; charset=UTF-8');
   }
   $detail=false;
   if (pq_array_key_exists('detail', $_REQUEST)) {
   	$detail=true;
   }
  if ($outMode!='pdf' and $outMode!='csv' and $outMode!='mpp' and $outMode!='word' and $outMode!='excel' and $outMode!='txt' and !$download and !$noHeader) {?> 
<!DOCTYPE html>
<?php }
   if ($outMode!='csv' and $outMode!='mpp' and $outMode!='word' and $outMode!='excel' and $outMode!='txt' and (!$download or $outMode=='pdf') and !$noHeader) {?>
<html style="overflow:auto">
<head>   
  <title><?php echo getPrintTitle();?></title>
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../view/css/jsgantt.css');?>" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../view/css/projeqtorIcons.css');?>" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../view/css/projeqtorPrint.css');?>" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../view/css/projeqtorFlat.css');?>" />
  <?php
    /* Build the mapping "var(--color-xxx)" => "#rrggbb" from the user theme
     * (session allColorsDynamicCss, fed by dynamicCss.js). Grey defaults are
     * used as a fallback so the PDF is never left with unresolved var() tokens
     * (e.g. when generated outside of an active GUI session).
     * This mapping is used both for projeqtorNew.css (html / WkHtml) and for the
     * lightweight projeqtorPrintTheme.css injected for every output including
     * html2pdf PDF, so the print/PDF gets the real theme colors. */
    $printThemeDefaults=array(
      '--color-reference'=>'#656565','--color-darker'=>'#4c4c4c','--color-dark'=>'#656565',
      '--color-medium'=>'#898989','--color-mediumlight'=>'#aeaeae','--color-light'=>'#d4d1d1',
      '--color-lighter'=>'#ededed','--color-text'=>'#656565','--color-white'=>'#ffffff',
      '--color-background'=>'#ffffff','--color-detail-header'=>'#ffffff',
      '--color-detail-header-text'=>'#656565','--color-detail-header-border'=>'#d4d1d1',
      '--color-section-title-text'=>'#656565','--color-section-title-border'=>'#656565',
      '--color-table-header'=>'#d4d1d1','--color-list-header'=>'#ffffff',
      // secondary theme colors (used by modernUI sub-section separators)
      '--color-secondary'=>'#898989','--color-darker-secondary'=>'#4c4c4c',
      '--color-dark-secondary'=>'#656565','--color-medium-secondary'=>'#898989',
      '--color-light-secondary'=>'#d4d1d1','--color-lighter-secondary'=>'#ededed'
    );
    $printColorMap=$printThemeDefaults;
    $colors=getSessionValue('allColorsDynamicCss');
    if ($colors) {
      $colorsArray=json_decode('['.$colors.']');
      if (is_array($colorsArray)) {
        foreach ($colorsArray as $o) {
          if (isset($o->key)) $printColorMap[$o->key]=pq_str_replace('*', '#', $o->value);
        }
      }
    }
    $arrayFrom=array();
    $arrayTo=array();
    foreach ($printColorMap as $printColorKey=>$printColorVal) {
      $arrayFrom[]='var('.$printColorKey.')';
      $arrayTo[]=$printColorVal;
    }
  ?>
  <?php /* projeqtorNew.css (full screen CSS) only for WkHtmlToPdf, which renders
           with a real browser engine. Plain html print and html2pdf both rely on
           projeqtorPrint.css + projeqtorPrintTheme.css so that print looks exactly
           like the pdf export. */ ?>
  <?php if (isNewGui() and $outMode=='pdf' and isWkHtmlEnabled() ) {?>
    <style type="text/css">
      <?php
      $css=file_get_contents('../view/css/projeqtorNew.css');
      $css=str_ireplace($arrayFrom, $arrayTo, $css);
      echo $css;
      ?>
    </style>
  <?php }?>
  <style type="text/css">
    <?php
    /* Theme aware print/PDF overrides. projeqtorPrint.css marks some rules
       (.section, headers, ...) "!important". Browser engines (plain html print
       and WkHtmlToPdf) honor it, so our theme must be "!important" too to win.
       html2pdf on the contrary CANNOT parse "!important" (it corrupts the value),
       so for that engine we strip it and rely on definition order instead.
       => identical rendering for print and pdf export. */
    $printThemeCss=file_get_contents('../view/css/projeqtorPrintTheme.css');
    $printThemeCss=str_ireplace($arrayFrom, $arrayTo, $printThemeCss);
    $isHtml2Pdf=($outMode=='pdf' and !isWkHtmlEnabled());
    if (!$isHtml2Pdf) {
      $printThemeCss=preg_replace('#/\*.*?\*/#s', '', $printThemeCss);      // drop comments
      $printThemeCss=preg_replace('/\s*;\s*/', ' !important;', $printThemeCss); // force each declaration
    }
    echo $printThemeCss;
    ?>
  </style>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../view/js/dynamicCss.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/chartJS/dist/chart.min.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/chartJS/plugins/datalabels/chartjs-plugin-datalabels.min.js');?>" ></script>
  <link rel="shortcut icon" href="../view/img/logo.ico" type="image/x-icon" />
  <link rel="icon" href="../view/img/logo.ico" type="image/x-icon" />
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
  <?php Security::writeMetaCSP();?>
<?php if (! isset($debugIEcompatibility) or $debugIEcompatibility==false) {?>  
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
<?php }?> 
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/dojo/dojo.js');?>"
    djConfig='modulePaths: {"i18n":"../../tool/i18n",
                            "i18nCustom":"../../plugin"},
              parseOnLoad: true,
              isDebug: <?php echo getBooleanValueAsString(Parameter::getGlobalParameter('paramDebugMode'));?>'></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/dojo/projeqtorDojo.js');?>"></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../view/js/jsgantt.js');?>"></script>
  <script type="text/javascript"> 
    var customMessageExists=<?php echo(file_exists(Plugin::getDir()."/nls/$currentLocale/lang.js"))?'true':'false';?>;
    dojo.require("dojo.dnd.Container");
    dojo.require("dijit.layout.BorderContainer");
    dojo.require("dijit.layout.ContentPane");
    dojo.require("dojo.parser");
    dojo.require("dojo.i18n");
    //dojo.require("dojo.date.locale");
    dojo.addOnLoad(function(){
      <?php 
        if (pq_array_key_exists('directPrint', $_REQUEST)) {
          echo "window.print();";
          //echo "window.close();";
        }
      ?>
      var printInNewWindow=<?php echo (getPrintInNewWindow())?'true':'false';?>;
      if (printInNewWindow) {
        var objTop=window.opener;
      } else {
    	  var objTop=top;
    	  objTop.window.document.title="<?php echo getPrintTitle();?>";
      }
      objTop.hideWait();
      //objTop.window.document.title="<?php echo getPrintTitle();?>";
      //window.document.title=applicationName;
      <?php if (isset($_REQUEST['page']) and $_REQUEST['page']=='planningPrint.php') {?>
        
        dojo.byId("leftGanttChartDIV_print").innerHTML=objTop.dojo.byId("leftGanttChartDIV").innerHTML;
        dojo.byId("leftGanttChartDIV_print").style.width=objTop.dojo.byId("leftGanttChartDIV").style.width;
        dojo.byId("leftside").style.top=0;
        dojo.byId("ganttScale").innerHTML="";
        dojo.byId("GanttChartDIV_print").style.left=dojo.byId("leftGanttChartDIV_print").offsetWidth+"px";
        dojo.byId("rightGanttChartDIV_print").innerHTML=objTop.dojo.byId("rightGanttChartDIV").innerHTML;
        dojo.byId("topGanttChartDIV_print").innerHTML=objTop.dojo.byId("topGanttChartDIV").innerHTML;
        dojo.byId("rightside").style.left='-1px';
        var height=dojo.byId("leftside").offsetHeight;
        height+=43;
        dojo.byId("GanttChartDIV_print").style.height=height+44+'px';
        //var g = new JSGantt.GanttChart('g',dojo.byId('ganttDiv'), window.top.g.getFormat()); 
      <?php }?>
    }); 
    
  </script>
</head>
<page backtop="100px" backbottom="20px" footer="page">
<?php $pdfZoom='80%';
      if (isset($_REQUEST['monthSpinner'])) {
        $pdfZoom='60%';
      } else if (isset($_REQUEST['periodType']) && $_REQUEST['periodType']=='month') {
        $pdfZoom='60%';
      }?>
<<?php echo ($printInNewPage or $outMode=='pdf' or (isset($outModeBack) and $outModeBack=='pdf')) ?'body':'div';?> style="-webkit-print-color-adjust: exact;<?php echo ($outMode=='pdf' and $pdfLib!='WkHtmlToPdf')?'font-size:'.$pdfZoom.';overflow:auto;':''; ?>" id="bodyPrint" class="tundra ProjeQtOrFlatGrey <?php if (isNewGui()) echo 'ProjeQtOrNewGui';?><?php if (isModernUi()) echo ' ProjeQtOrModern';?><?php if ($outMode=='pdf') echo ' ProjeQtOrPdf';?>" onload="window.top.hideWait();">
  <?php 
  }
  $page=$_REQUEST['page']??'';
  $splitPage=pq_explode('?',$page);
  if (pq_substr($page,0,17)=='../report/object/') {
    if (file_exists($splitPage[0])) {
       $rpt=file_get_contents($splitPage[0]);
       if (pq_strpos($rpt,"templateReportExecute.php")>0 and ! Plugin::isPluginEnabled('templateReport')) {     
         // Template report plugin disabled, but custom report defined for object and is template one
         $page="../view/objectDetail.php".((count($splitPage)>1)?'?'.$splitPage[1]:'');
       }
    } else {
       $page="../view/objectDetail.php".((count($splitPage)>1)?'?'.$splitPage[1]:'');
    }
  }
  $page=pq_str_replace('../report/../tool/','../tool/',$page);
  securityCheckPage($page);
  $includeFile=$page;
  if (! pq_substr($page,0,3)=='../') {
    $includeFile='../view/'.$page;
  }
  securityCheckPage($includeFile);
  $pos = pq_strpos($includeFile, '?');
  if ($pos !== FALSE) {
    $params=pq_substr($includeFile, $pos + 1);
    $includeFile=pq_substr($includeFile, 0, $pos);
    $paramArray=pq_explode('&',$params);
    foreach ($paramArray as $param)
    {
      $par=pq_explode('=',$param);
      $_REQUEST[$par[0]]=$par[1];
    }
  }
  $outModeBack=$outMode;
  if ($outMode=='pdf' and isWkHtmlEnabled()) { $outMode='html';}
  include $includeFile;
  $outMode=$outModeBack;
  if ($outMode!='csv' and $outMode!='mpp' and $outMode!='word' and $outMode!='excel' and $outMode!='txt' and (!$download or $outMode=='pdf') and !$noHeader) {?>
</<?php echo ($printInNewPage or $outMode=='pdf' or (isset($outModeBack) and $outModeBack=='pdf'))?'body':'div';?>>
</page>
</html>
<?php
  } 
  finalizePrint();
?>
<?php function finalizePrint() {
  global $outMode, $download, $includeFile, $orientation, $printInfo,$templateOutputFileName, $attach, $facturxMode;
  $pdfLib='html2pdf';
  //$pdfLib='mPdf';

  if (isWkHtmlEnabled()) {
    $pdfLib='WkHtmlToPdf';
  }
  $printInfo=array();
  $printInfo['page']=(isset($_REQUEST['page']))?$_REQUEST['page']:'';
  $printInfo['objectClass']=(isset($_REQUEST['objectClass']))?$_REQUEST['objectClass']:'';
  $printInfo['objectId']=(isset($_REQUEST['objectId']))?$_REQUEST['objectId']:'';
  $printInfo['reportName']=(isset($_REQUEST['reportName']))?$_REQUEST['reportName']:'';
  //$pdfLib='dompdf';
  $outputFileName=null;
  $customName=null;
  if (file_exists('../report/object/customReportFunctions.php')) {
    include_once '../report/object/customReportFunctions.php';
  }
  if (isset($_REQUEST['objectClass']) and isset($_REQUEST['objectId']) and isset($_REQUEST['page']) 
  and ($_REQUEST['page']=='objectDetail.php' 
      or $_REQUEST['page']=='../report/object/'.$_REQUEST['objectClass'].'.php'
      or $_REQUEST['page']=='../report/object/'.$_REQUEST['objectClass'].'_CustomReport.php' )) {
    $objectClass=$_REQUEST['objectClass'];
    if ($objectClass=='Replan') $objectClass='Project';
    if ($objectClass=='ProductVersionhasChild') $objectClass = 'ProductVersion';
    if ($objectClass=='ComponentVersionhasChild') $objectClass = 'ComponentVersion';
    $objectId=$_REQUEST['objectId'];
    $obj=new $objectClass($objectId);
    $outputFileName=i18n($objectClass).' ';
    if (property_exists($obj, 'reference') and $obj->reference) {
      $outputFileName.=$obj->reference;
    } else {
      $outputFileName.=$obj->id;
      if (property_exists($obj, 'name')) {
        //$outputFileName.=' ('.$obj->name.')';
      }
    }
    $outputFileName.=".pdf";
    $outputFileName=Security::checkValidFileName($outputFileName,false);
    if ($templateOutputFileName) {
      $customName=$templateOutputFileName;
      $outputFileName=$templateOutputFileName;
    } else if (function_exists('getCustomReportName')) {
      $customName=getCustomReportName($objectClass,$objectId,'detail','pdf',$outputFileName); // May return null or empty string to keep default name
      if ($customName) $outputFileName=$customName;
    }
  } else if (isset($_REQUEST['page']) and $_REQUEST['page']=='../tool/jsonQuery.php' and isset($_REQUEST['objectClass']) ) {
    $objectClass=$_REQUEST['objectClass'];
    $outputFileName=i18n('menu'.$objectClass).'_'.date('Ymd_His');
    $outputFileName.=".pdf";
    $outputFileName=Security::checkValidFileName($outputFileName,false);
    if ($templateOutputFileName) {
      $customName=$templateOutputFileName;
      $outputFileName=$templateOutputFileName;
    } else if (function_exists('getCustomReportName')) {
      $customName=getCustomReportName($objectClass,null,'list','pdf',$outputFileName); // May return null or empty string to keep default name
      if ($customName) $outputFileName=$customName;
    }
  } else if (isset($_REQUEST['reportName'])) {
    $outputFileName=$_REQUEST['reportName'].'_'.date('Ymd_His');
    if ($outMode=='excel') {
      $typeOfExport = Parameter::getUserParameter("typeExportXLSorODS");
      $outputFileName .= ($typeOfExport=="Excel2007"?".xlsx":".ods");
      $content=ob_get_contents();
      if ($templateOutputFileName) {
        $customName=$templateOutputFileName;
        $outputFileName=$templateOutputFileName;
      } else if (function_exists('getCustomReportName')) {
        $customName=getCustomReportName($_REQUEST['reportName'],null,'report','xlsx',$outputFileName); // May return null or empty string to keep default name
        if ($customName) $outputFileName=$customName;
      }
      if (pq_strpos($content,'<table _excel-name=')!==false or pq_strpos($content,'<table  _excel-name=')!==false) { // Target is Excel and stype not transformed in xlsx file
        ob_clean();
        if (version_compare(phpversion(), '8.0.0', '>=') ) require_once('../external/HtmlPhpExcel/vendor/autoload.php');
        else require_once('../external/HtmlPhp7Excel/vendor/autoload.php');
        //$htmlPhpExcel = new \Ticketpark\HtmlPhpExcel\HtmlPhpExcel(iconv('UTF-8', 'Windows-1252',$content));
        $htmlPhpExcel = new \Ticketpark\HtmlPhpExcel\HtmlPhpExcel(encodeForExcel($content));
        $outputFileName=pq_str_replace("\0",'',$outputFileName);
        $htmlPhpExcel->process()->output($outputFileName,($typeOfExport=="Excel2007"?"xlsx":"ods"));
      }
    } else {
      $outputFileName.=".pdf";
      if ($templateOutputFileName) {
        $customName=$templateOutputFileName;
        $outputFileName=$templateOutputFileName;
      } else if (function_exists('getCustomReportName')) {
        $customName=getCustomReportName($_REQUEST['reportName'],null,'report','pdf',$outputFileName); // May return null or empty string to keep default name
        if ($customName) $outputFileName=$customName;
      }
    }
  }
  if (isset($pdfNamePrefix) and !$customName) $outputFileName=$pdfNamePrefix.$outputFileName;
  if (!$outputFileName and $templateOutputFileName) $outputFileName=pathinfo($templateOutputFileName, PATHINFO_FILENAME).'.pdf';
  if ($outMode=='pdf') {
    $content = ob_get_clean();   
    $content = htmlPrepareImagesForPdf($content);
    if ($pdfLib=='html2pdf') {
      /* HTML2PDF way */
      $pdfTrace=(RequestHandler::getValue('pdfTrace')=='1');
      $pdfTraceTime=microtime(true);
      if ($pdfTrace) {
        debugTraceLog(
          'PDF TRACE html2pdf start | htmlSize='.pq_strlen($content).
          ' | img='.substr_count($content, '<img').
          ' | table='.substr_count($content, '<table')
        );
      }
      require_once '../external/html2pdf/vendor/autoload.php';
      //require_once '../external/html2pdf/src/MyPdf.php';
      //$html2pdf = new MyPdf($orientation,'A4','en');
      $html2pdf = new HTML2PDF($orientation,'A4','en');
      if ($pdfTrace) {
        debugTraceLog('PDF TRACE html2pdf construct='.round(microtime(true)-$pdfTraceTime, 3).'s');
        $pdfTraceTime=microtime(true);
      }
      
      //$html2pdf->setModeDebug();
      $html2pdf->pdf->SetDisplayMode('fullpage');
      $html2pdf->pdf->SetMargins(10,10,10,10);
      $html2pdf->setTestTdInOnePage(false);
      $fontForPDF=Parameter::getGlobalParameter('fontForPDF');
      if (!$fontForPDF) $fontForPDF='freesans';
      if ($facturxMode){
        //need force font for respect format EN16931
        $html2pdf->pdf->setFontSubsetting(false);
        $html2pdf->setDefaultFont('freesans');
      }else{
        $html2pdf->setDefaultFont($fontForPDF);
      }
      $html2pdf->setTestTdInOnePage(false);
      //$html2pdf->setModeDebug(); 
      //$content=pq_str_replace("à","&agrave;",$content);
//traceExecutionTime($includeFile,true);

      $html2pdf->writeHTML($content);
      if ($pdfTrace) {
        debugTraceLog('PDF TRACE html2pdf writeHTML='.round(microtime(true)-$pdfTraceTime, 3).'s');
        $pdfTraceTime=microtime(true);
      }
     // $html2pdf->writeHTML($html2pdf->getHtmlFromPage($content)); 
      if (ob_get_length()) {
        ob_end_clean();
      }
      if ($facturxMode){
        //case when facturX  export == YES
        //call external facturX here because before create bug with autoload of projeqtor
        global $hideAutoloadError;
        $hideAutoloadError = true;
        require_once '../external/factur-x/autoload.php';
        //get pdf content in string ( S ) for no input back
        $pdfBinary = $html2pdf->Output('', 'S');
        ob_start();
        if(!isset($objectId))$objectId = RequestHandler::getId("objectId");
        
        $facturxError = FacturX::outputFromBillId((int)$objectId, $attach);
        $xml = ob_get_clean();
        $xmlTrim = ltrim((string)$xml);
        if (!empty($facturxError)) {
          $msg = $facturxError;
          
          if ($attach) {
            returnFacturXAttachResult($msg, true);
          } else {
            stopPrintFacturXError($msg);
          }
        }
        if ($xmlTrim === '' || strpos($xmlTrim, '<?xml') !== 0) {
          $msg = i18n('facturXMessageError');
          
          if ($attach) {
            returnFacturXAttachResult($msg, true);
          } else {
            stopPrintFacturXError($msg);
          }
        }
        
        try {
          $validator = new \Atgp\FacturX\XsdValidator();
          $validator->validateWithException($xml);
          
          $writer = new \Atgp\FacturX\Writer();
          $facturxPdf = $writer->generate(
              $pdfBinary, //  Content of the PDF invoice
              $xml, //        Content of the XML invoice
              null, //        One of \Atgp\FacturX\Facturx::PROFIL_* (null for auto-detection)
              true, //        check Factur-X XML against official XSD
              [],   //        additionalAttachments
              true, //        Add Factur-X logo on PDF first page according to Factur-X profile
              'Data'//        the embarkation relationship, must be Data|Source|Alternativ
              );
          
          $pdfBinary = $facturxPdf; //replace PDF by Factur-X
          
        } catch (\Throwable $e) {
          $msg = 'Factur-X impossible okok : ' . $e->getMessage();
          
          if ($attach) {
            returnFacturXAttachResult($msg, true);
          } else {
            stopPrintFacturXError($msg);
          }
        }
        if(!$attach){
          header('Content-Type: application/pdf');
          header('Content-Disposition: '.($download ? 'attachment' : 'inline').'; filename="'.$outputFileName.'"');
          header('Content-Length: '.strlen($pdfBinary));
          echo $pdfBinary;
          exit;
        }
        //$html2pdf->writeHTML($pdfBinary);
      }
      
      if (!$outputFileName) $outputFileName='document.pdf';
      if ($attach) {
        $attachment = new Attachment();
        $attachment->refId = $objectId;
        $attachment->refType = $_REQUEST['objectClass'];
        $attachment->idUser = getCurrentUserId();
        $attachment->idPrivacy = 1;
        
        $ress = new Resource(getCurrentUserId());
        $attachment->idTeam = $ress->idTeam;
        $attachment->fileName = Security::checkValidFileName($outputFileName, false);
        $attachment->fileName = Security::checkValidFileName($attachment->fileName, false, true);
        $attachment->creationDate = date("Y-m-d H:i:s");
        $attachment->type = 'file';
        $attachment->mimeType = 'application/pdf';
        
        $subResult = $attachment->save();
        $newId = $attachment->id;
        
        $pathSeparator = Parameter::getGlobalParameter('paramPathSeparator');
        $attachmentDirectory = Parameter::getGlobalParameter('paramAttachmentDirectory');
        
        $uploaddir = $attachmentDirectory . $pathSeparator . "attachment_" . $newId . $pathSeparator;
        if (!file_exists($uploaddir)) {
          mkdir($uploaddir, 0777, true);
        }
        
        $paramFilenameCharset = Parameter::getGlobalParameter('filenameCharset');
        if ($paramFilenameCharset) {
          $uploadfile = $uploaddir . iconv("UTF-8", $paramFilenameCharset . '//TRANSLIT//IGNORE', $attachment->fileName);
        } else {
          $uploadfile = $uploaddir . $attachment->fileName;
        }
        if (substr($uploadfile, 0, 2) == '..') {
          $uploadfile = str_replace(array("\\view", "/view"), "", __DIR__) . substr($uploadfile, 2);
        }
        
        if ($facturxMode) {
          $bytes = file_put_contents($uploadfile, $pdfBinary);
          
          if ($bytes === false) {
            if (!empty($attachment->id) && method_exists($attachment, 'delete')) {
              @$attachment->delete();
            }
            returnFacturXAttachResult("Erreur lors de l'écriture du fichier Factur-X.", true);
          }
          
          clearstatcache(true, $uploadfile);
          $size = filesize($uploadfile);
          if ($size === false || $size <= 0) {
            if (!empty($attachment->id) && method_exists($attachment, 'delete')) {
              @$attachment->delete();
            }
            returnFacturXAttachResult("Le fichier Factur-X généré est vide ou invalide.", true);
          }
          
          Security::checkEvilFile($uploadfile);
          $attachment->fileSize = $size;
          $attachment->subDirectory = pq_str_replace(Parameter::getGlobalParameter('paramAttachmentDirectory'),'${attachmentDirectory}',$uploaddir);
          $attachment->save();
          
          returnFacturXAttachResult(i18n("operationDone"), false);
        } else {
          if ($pdfTrace) $pdfTraceTime=microtime(true);
          $html2pdf->Output($uploadfile, 'FI');
          if ($pdfTrace) debugTraceLog('PDF TRACE html2pdf output='.round(microtime(true)-$pdfTraceTime, 3).'s');
          // --- SAVE subDirectory !  ---
          $attachment->fileSize = filesize($uploadfile);
          Security::checkEvilFile($uploadfile);
          $attachment->subDirectory = pq_str_replace(Parameter::getGlobalParameter('paramAttachmentDirectory'),'${attachmentDirectory}',$uploaddir);
          $attachment->save();
          // -------------------------------------------------------------
        }
      } else if ($download and !$attach) {
        if(!$facturxMode){
          if ($pdfTrace) $pdfTraceTime=microtime(true);
          $html2pdf->Output($outputFileName,'D');
          if ($pdfTrace) debugTraceLog('PDF TRACE html2pdf output='.round(microtime(true)-$pdfTraceTime, 3).'s');
        }
      } else {
        if(!$facturxMode){
          if ($pdfTrace) $pdfTraceTime=microtime(true);
          $html2pdf->Output($outputFileName);
          if ($pdfTrace) debugTraceLog('PDF TRACE html2pdf output='.round(microtime(true)-$pdfTraceTime, 3).'s');
        }
      }
    } else if ($pdfLib=='mPdf') {
      /* MPDF way */
      require_once '../external/mPdf/autoload.php';
      //$html2pdf = new //myHtml2Pdf($orientation,'A4','en');
      $mPdf = new \Mpdf\Mpdf(['orientation' => $orientation]); 
      
      //$html2pdf->pdf->SetDisplayMode('fullpage');
      //$html2pdf->pdf->SetMargins(10,10,10,10);
      //$fontForPDF=Parameter::getGlobalParameter('fontForPDF');
      //if (!$fontForPDF) $fontForPDF='freesans';
      //$html2pdf->setDefaultFont($fontForPDF);
      //$html2pdf->setTestTdInOnePage(false);

       $mPdf->WriteHTML($content);
     
      if (ob_get_length()) {
        ob_end_clean();
      }
      if (!$outputFileName) $outputFileName='document.pdf';
      if ($download) {
        $mPdf->Output($outputFileName,'D');
      } else {
        $mPdf->Output($outputFileName, 'I');
      }
//traceExecutionTime($includeFile);
    } else if ($pdfLib=='dompdf') {
    /* DOMPDF way */
      require_once("../external/dompdf/dompdf_config.inc.php");
      $dompdf = new DOMPDF();
      $dompdf->load_html($content);
      $dompdf->render();
      $dompdf->stream("sample.pdf");
    } else if ($pdfLib=='WkHtmlToPdf') {
      $path=Parameter::getGlobalParameter('pathToWkHtmlToPdf');
      $smallMargin=false;
      //$htmlFile='../files/report/test.html';
      //$pdfFile='../files/report/test.pdf';
      chdir ("../files");
      $suffix=getCurrentUserId().'_'.date('Ymd_His');
      $htmlFile="pdfExport_$suffix.html";
      $pdfFile="report/pdfExport_$suffix.pdf";
      $exportFileName=($outputFileName)?$outputFileName:'document.pdf';
      kill ($htmlFile);
      writeFile($content, $htmlFile);
      $options='--orientation '.(($orientation=='P')?'Portrait':'Landscape');
      $options.=" --encoding 'utf-8'";
      $options.=" --page-size A4";
      if ($includeFile=='objectDetail.php') $options.=' --zoom 1.46';
      //$options.=' --zoom '.(($smallMargin)?'1.24':'1.18');
      //$options.=' --zoom '.(($smallMargin)?'1.24':'1.46');
      $options.=' --title "'.basename($exportFileName).'"';
      $margin=($smallMargin)?'5mm':'10mm';
      $options.=" --margin-bottom $margin --margin-left $margin --margin-right $margin --margin-top $margin";
      exec("\"$path\" $options $htmlFile $pdfFile");
      if (ob_get_length()) {
        ob_end_clean();
      }
      
      if ($download) {
        header('Content-Description: File Transfer');
        header('Content-Type: application/octet-stream');
        header('Content-Disposition: attachment; filename="'.basename($exportFileName).'"');
        header('Expires: 0');
        header('Cache-Control: must-revalidate');
        header('Pragma: public');
        header('Content-Length: ' . filesize($pdfFile));
        readfile($pdfFile);
      } else {
        header('Content-Type: application/pdf');
        header('Cache-Control: private, must-revalidate, post-check=0, pre-check=0, max-age=1');
        //header('Cache-Control: public, must-revalidate, max-age=0'); // HTTP/1.1
        header('Pragma: public');
        header('Expires: Sat, 26 Jul 1997 05:00:00 GMT'); // Date in the past
        header('Last-Modified: '.gmdate('D, d M Y H:i:s').' GMT');
        header('Content-Disposition: inline; filename="'.basename($exportFileName).'"');
        readfile($pdfFile);
      }
      
      kill ($htmlFile);
      kill ($pdfFile);
    }
  }
}
function isWkHtmlEnabled() {
  $wkFile=Parameter::getGlobalParameter('pathToWkHtmlToPdf');
  if ($wkFile) {
    if (file_exists($wkFile)) {
      return true;
    } else {
      debugTraceLog("incorrect path to WkHtmlToPdf executable '$wkFile' (file does not exist)");
      return false;
    }
  } 
  return false;
}

function stopPrintFacturXError(string $message): void {
  
  while (ob_get_level() > 0) { @ob_end_clean(); }
  
  header_remove();
  
  http_response_code(200);
  header('Content-Type: text/html; charset=UTF-8');
  header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
  
  $msg = html_entity_decode($message, ENT_QUOTES | ENT_HTML5, 'UTF-8');
  $msg = htmlspecialchars($msg, ENT_QUOTES, 'UTF-8');
  
  echo '<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>';
  echo '<div style="font-family:Arial;padding:12px">';
  echo '<b>Factur-X impossible</b><br>';
  echo '<div style="margin-top:6px">'.$msg.'</div>';
  echo '</div>';
  
  echo '<script>';
  echo 'try {';
  echo '  if (window.top && window.top.hideWait) window.top.hideWait();';
  echo '  if (window.opener && window.opener.hideWait) window.opener.hideWait();';
  echo '} catch(e) {}';
  echo '</script>';
  
  echo '</body></html>';
  exit;
}

function returnFacturXAttachResult(string $message, bool $isError = true): void {
  while (ob_get_level() > 0) {
    @ob_end_clean();
  }
  
  if (function_exists('header_remove')) {
    header_remove();
  }
  
  header('Content-Type: text/html; charset=UTF-8');
  header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
  
  $msg = json_encode($message);
  
  echo '<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body><script>';
  echo 'try {';
  echo '  var objTop = window.top || window.parent || window.opener;';
  echo '  if (objTop && objTop.hideWait) objTop.hideWait();';
  
  // redirect to attach table
  echo '  try { if (objTop && objTop.redirectOnTab) objTop.redirectOnTab("", "", "fichier"); } catch(e) {}';
  
  // refresh attach table
  echo '  try {';
  echo '    if (objTop && objTop.loadContent && objTop.dojo && objTop.dojo.byId("objectClass")) {';
  echo '      objTop.loadContent("objectDetail.php?refreshAttachments=true", objTop.dojo.byId("objectClass").value + "_Attachment", "listForm");';
  echo '    }';
  echo '  } catch(e) {}';
  
  if ($isError) {
    echo '  if (objTop && objTop.showAlert) objTop.showAlert(' . $msg . ');';
    echo '  else if (objTop && objTop.showError) objTop.showError(' . $msg . ');';
    echo '  else alert(' . $msg . ');';
  } else {
    echo '  if (objTop && objTop.showInfo) objTop.showInfo(' . $msg . ');';
    echo '  else alert(' . $msg . ');';
  }
  
  echo '} catch(e) { alert(' . $msg . '); }';
  echo '</script></body></html>';
  exit;
}

?>
