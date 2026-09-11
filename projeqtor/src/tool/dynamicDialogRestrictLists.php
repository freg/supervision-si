<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2016 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
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
include_once ("../tool/projeqtor.php");
$idProject=RequestHandler::getId('idProject');
$listOfValues=ListHideValue::getListOfValues();
?>
<div style="height:50px;width:600px;" class="title">
  <table >
    <tr>
      <td style="width:30%; text-align:right;padding-right:10px"><?php echo i18n("menuListOfValues");?></td>
      <td style="width:50%">
        <input type='hidden' id='selectedListProject' value='<?php echo $idProject;?>' />
        <select dojoType="dijit.form.FilteringSelect" 
  				<?php echo autoOpenFilteringSelect();?>
  				id="selectedList" name="selectedList" 
  				class="input" value="" >
  				<option value=" "></option>
  				<?php foreach ($listOfValues as $val=>$name) {?>
  				<option value="<?php echo $val;?>"><?php echo $name;?></option>
  				<?php }?>
          <script type="dojo/connect" event="onChange" args="evt">
            callback=function() {};
            loadDiv("../tool/getListOfValues.php?list="+this.value+"&idProject=<?php echo $idProject;?>", "RestrictListList", null, callback);
          </script>
        </select>
      </td>
      <td style="width:50%">&nbsp;</td>
    </tr>
  </table>
</div>
<div style="height:400px;overflow-y:auto;margin:10px;border:1px solid #eeeeee;user-select:none" id="RestrictListList">

</div>