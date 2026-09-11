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

?>
<html>
	<head>
		<meta charset="UTF-8">
  	<meta http-equiv="content-type" content="text/html; charset=UTF-8" />
  	<title><?php echo (Parameter::getGlobalParameter('paramDbDisplayName'))?Parameter::getGlobalParameter('paramDbDisplayName'):i18n("applicationTitle");?></title>
 		<link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../view/css/projeqtor.css');?>" />
    <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../view/css/projeqtorNew.css');?>" />
   	<script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../view/js/dynamicCss.js');?>" ></script>
   	<script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/dojox/mobile/deviceTheme.js');?>" data-dojo-config="mblUserAgent: 'Custom'"></script>
   	<script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../view/js/projeqtor.js');?>" ></script>
   	<script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../view/js/projeqtorFormatter.js');?>" ></script>
   	<script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/dojo/dojo.js');?>"
    djConfig='modulePaths: {"i18n":"../../tool/i18n",
                            "i18nCustom":"../../plugin"},
              parseOnLoad: true, 
              isDebug: <?php echo getBooleanValueAsString(Parameter::getGlobalParameter('paramDebugMode'));?>'></script>
   	<script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/dojo/projeqtorDojo.js');?>"></script>
   	<script type="text/javascript"> 
   	  
   	</script>
   	<style>
     	.msgSBclassSubToday {
        color: #f1a874;
        background-color: #545381;
        font-size: 12pt;
        font-weight: lighter;
      }
      .msgSBclassSub {
        position: absolute;
        background-color: #545381;
        width: 100%;
        text-align: center;
      }
      .backgroundColor {
       background-color: #545381;
       color:#e97b2c;
      }
    </style>
  </head>
	<body class="ProjeQtOrFlatBlue backgroundColor" onload="setDisplaySM();">
		<table class="projeqtorReference" style="width:100%;height:100%">
      <tr height="100px" style="vertical-align: middle;">
        <td width="20%" >&nbsp;</td>
        <td width="60%"></td>
        <td width="20%"></td>
      </tr>
      <tr height="100%" style="vertical-align: top;align:center">
        <td width="20px" >&nbsp;</td>
        <td width="60%" style="cursor:pointer;position:relative" onclick="window.open(&quot;https://subscription.projeqtor.org&quot;, &quot;_blank&quot;).focus();">
        	<img alt="User Manual" src="../docs/user/html_en/_images/INDEX_ZONE_CouvManuel.png">   
        	<div style="position: absolute; top:20px;width:738px; text-align:center;font-size:120%">
        	<?php
        	  if (pq_substr($currentLocale,0,2)=='fr') echo "L'accès au manuel utilisateur est réservé aux instances avec souscription";
        	  else echo "Access to the user manual is restricted to instances with subscription service.";
        	?>
        	</div>
        </td>
        <td width="20%"></td>
    </table>
    
	</body>
</html>