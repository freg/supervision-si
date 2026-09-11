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
require_once "../tool/projeqtor_string.php";

function getGraphImgName($root) {
  global $reportCount;
  //$user=getSessionUser();
  $reportCount+=1;
  $name=Parameter::getGlobalParameter('paramReportTempDirectory');
  $name.="/user" . getCurrentUserId() . "_";
  $name.=$root . "_";
  $name.=date("Ymd_His") . "_";
  $name.=$reportCount;
  $name.=".png";  
  return $name;
}

function testGraphEnabled() {
  global $graphEnabled;
  if ($graphEnabled) {
    return true;
  } else {
    //echo '<table width="95%" align="center"><tr><td align="center">';
    //echo '<img src="../view/img/GDnotEnabled.png" />'; 
    //echo '</td></tr></table>';
    return false;
  }  
}

function checkNoData($result,$month=null) {
  global $outMode, $cronnedScript;
  if (count($result)==0) {
    if ( ($outMode=='pdf' and $cronnedScript!==true) or $outMode=='excel') { ob_clean(); }
    echo '<table width="95%" align="center"><tr height="50px"><td width="100%" align="center">';
    echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
    if(!$month){
      echo i18n('reportNoData');
    }else{
      echo i18n('reportNoDataForPeriod')." ".$month;
    }
    echo '</div>';
    echo '</td></tr></table>';
    if ($outMode=='pdf' and $cronnedScript!==true ) {
      finalizePrint();
    }
    return true;
  }
  return false;
}

function hex2rgb($hex) {
  $hex = pq_str_replace("#", "", $hex);
  if(pq_strlen($hex) == 3) {
    $r = hexdec(pq_substr($hex,0,1).pq_substr($hex,0,1));
    $g = hexdec(pq_substr($hex,1,1).pq_substr($hex,1,1));
    $b = hexdec(pq_substr($hex,2,1).pq_substr($hex,2,1));
  } else {
    $r = hexdec(pq_substr($hex,0,2));
    $g = hexdec(pq_substr($hex,2,2));
    $b = hexdec(pq_substr($hex,4,2));
  }
  $rgb = array('R'=>$r, 'G'=>$g, 'B'=>$b);
  //return implode(",", $rgb); // returns the rgb values separated by commas
  return $rgb; // returns an array with the rgb values
}

function getFontLocation($font) {
  $current=dirname_recursive(__FILE__,2);
  return "$current/external/pChart2/fonts/$font.ttf";
}
function dirname_recursive($path, $count=1){
  if ($count > 1){
    return dirname(dirname_recursive($path, --$count));
  }else{
    return dirname($path);
  }
}
$page=1;
$lastName=null;
function excelName($name=null, $quote='"') {
  global $lastName, $page;
  if (!$page) $page=0;
  if (!$name) $name=RequestHandler::getValue('reportName');
  $name=pq_str_replace('/','-',$name);
  if ($name==$lastName) {
    $page++;
    $name.=" ($page)";
  } else {
    $lastName=$name;
  }
  $result= ' _excel-name='.$quote.pq_mb_substr(pq_str_replace(' - ',' ',$name),0,31).$quote.' ';
  return $result;
}
function excelFormatCell($cellType='data',$width=null, $color=null, $bgcolor=null, $bold=null, $hAlign=null, $vAlign=null,$fontSize=null,$valueType=null,$noWrap=false, $noBorder=false) {
  // cellType = data, header, subheader
  $format="";
  if ($width) {
    $format=" _excel-dimensions='{"
        .'"column":{"width":'.$width.'}'
        ."}' ";
  }
  $borderColor="aaaaaa";
  if (!$color) $color='000000';
  else $color=pq_ltrim($color,'#');
  if ($bgcolor) {
    $bgcolor=pq_ltrim($bgcolor,'#');
  } else {
    if ($cellType=='data') {
      $bgcolor='ffffff';
    } else if ($cellType=='header') {
      $bgcolor=getColorFromTheme('header');
      $color='ffffff';
      if (! $hAlign) $hAlign='center';
      if (! $vAlign) $vAlign='center';
      if ($bold===null) $bold=true;
    } else if ($cellType=='subheader') {
      $bgcolor=getColorFromTheme('subheader');
      $color='ffffff';
      $borderColor=getColorFromTheme('rowheader');
    } else if ($cellType=='subheaderred') {
      $bgcolor=getColorFromTheme('subheader');
      $color='F50000';
      $borderColor=getColorFromTheme('rowheader');
    } else if ($cellType=='rowheader') {
      $bgcolor=getColorFromTheme('rowheader');
      $color=getColorFromTheme('dark');
      if (! $hAlign) $hAlign='left';
      if (! $vAlign) $vAlign='center';
    }
    if ($bgcolor=='eeeeee') {
      $color='000000';
      $borderColor='aaaaaa';
    }
  }
  if (! $vAlign) $vAlign='center';
  if (! $hAlign) $hAlign='center';
  if ($bold===null) $bold=false;
  if (!$fontSize) $fontSize='11';
  $numberFormat='';
  if ($valueType=='work') {
    $thd=getSessionValue('browserLocaleThousandSeparator');
    if ($thd=='.') $thd='';
    $numberFormat='#'.$thd.'##0.0# \"'.Work::displayShortWorkUnit().'\"';
  } else if ($valueType=='imput') {
    $thd=getSessionValue('browserLocaleThousandSeparator');
    if ($thd=='.') $thd='';
    $numberFormat='#'.$thd.'##0.0# \"'.Work::displayShortImputationUnit().'\"';
    //gautier #7035
  } else if ($valueType=='cost') {
    $thd=getSessionValue('browserLocaleThousandSeparator');
    if ($thd=='.') $thd='';
    $currency=Parameter::getGlobalParameter('currency');
    $currencyPosition=Parameter::getGlobalParameter('currencyPosition');
    if($currency=='€')$currency='&euro;';
    if ($currencyPosition=='before'){
      $numberFormat='\"'.$currency.'\"#'.$thd.'##0.00';
    }else{
      $numberFormat='#'.$thd.'##0.00 \"'.$currency.'\"';
    }
  } else if ($valueType=='percent') {
    $numberFormat='0%';
  }
  $format.=" _excel-styles='{"
      .'"alignment":{"horizontal":"'.$hAlign.'","vertical":"'.$vAlign.'"'.(($noWrap)?'':',"wrapText":true').'},'
      .'"font":{"size":'.$fontSize.',"color":{"rgb":"'.$color.'"}'.(($bold==true)?',"bold":true':'').'},'
      .'"fill":{"fillType":"solid","color":{"rgb":"'.$bgcolor.'"}}'
      .(($noBorder)?'':',"borders":{"outline":{"borderStyle":"thin","color":{"rgb":"'.$borderColor.'"}}}')
      .(($numberFormat)?',"numberFormat":{"formatCode":"'.$numberFormat.'"}':'')
    ."}' ";
  
  return $format;
}
function excelFormatLine($height=null) {
  // cellType = data, header, subheader
  $foramt="";
  if ($height) {
    $format="_excel-dimensions='{"
        .' "row":{"rowHeight":'.$height.'}'
      ."}' ";
  }
  return $format;
}
function getColorFromTheme($val) {
  global $newGuiColors;
  $array=array(
      "ProjeQtOrFlatBlue"=>array("dark"=>"545381","header"=>"7b769c","subheader"=>"a6a0bc","rowheader"=>"cdcadb"),
      "ProjeQtOrFlatRed"=>array("dark"=>"833e3e","header"=>"b07878","subheader"=>"bda1a6","rowheader"=>"ddcdce"),
      "ProjeQtOrFlatGreen"=>array("dark"=>"537665","header"=>"779a84","subheader"=>"86a790","rowheader"=>"c9dbce"),
      "ProjeQtOrFlatGrey"=>array("dark"=>"656565","header"=>"898989","subheader"=>"AEAEAE","rowheader"=>"D4D1D1"),
      "default"=>array("dark"=>"000000","header"=>"909090","subheader"=>"eeeeee","rowheader"=>"eeeeee")
  );
  if ($newGuiColors) {
    if (isset($newGuiColors['--color-darker'])) $array["default"]['dark']=$newGuiColors['--color-darker'];
    if (isset($newGuiColors['--color-darker'])) $array["default"]['header']=$newGuiColors['--color-darker'];
    if (isset($newGuiColors['--color-medium'])) $array["default"]['subheader']=$newGuiColors['--color-medium'];
    if (isset($newGuiColors['--color-light'])) $array["default"]['rowheader']=$newGuiColors['--color-light'];
  }
  $theme=Parameter::getUserParameter('theme');
  $row=(isset($array[$theme]))?$array[$theme]:$array['default'];
  $result=(isset($row[$val])) ?$row[$val]:'ff0000';
  return $result;
}
$newGuiColors=null;
$allColors=getSessionValue('allColorsDynamicCss');
if ($allColors) {
  $colors=json_decode('['.$allColors.']',true);
  $newGuiColors=array();
  foreach ($colors as $col) {
    $newGuiColors[$col['key']]=pq_str_replace('*','',$col['value']);
  }
}

$rgbPalette=array(
    6=>array('B'=>200, 'G'=>100, 'R'=>100),
    7=>array('B'=>100, 'G'=>200, 'R'=>100),
    8=>array('B'=>100, 'G'=>100, 'R'=>200),
    9=>array('B'=>200, 'G'=>200, 'R'=>100),
    10=>array('B'=>200, 'G'=>100, 'R'=>200),
    11=>array('B'=>100, 'G'=>200, 'R'=>200),
    0=>array('B'=>250, 'G'=> 50, 'R'=> 50),
    1=>array('B'=> 50, 'G'=>250, 'R'=> 50),
    2=>array('B'=> 50, 'G'=> 50, 'R'=>250),
    3=>array('B'=>250, 'G'=>250, 'R'=> 50),
    4=>array('B'=>250, 'G'=> 50, 'R'=>250),
    5=>array('B'=> 50, 'G'=>250, 'R'=>250)
);
?>