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

/* ============================================================================
 * Preview pane of the document explorer : the file of the last version of the
 * selected document, shown in place of the object detail.
 *
 * Loaded by loadContent() into detailDiv with the fields of listForm, exactly
 * where view/objectDetail.php goes otherwise.
 *
 * Nothing is streamed from here. The file is served by tool/download.php, which
 * resolves the last version of a Document on its own (l. 105-111), sends the
 * right content type, answers inline when showHtml is set (l. 158) and enforces
 * the read rights of the user (l. 74). Embedding a file this way is the pattern
 * of view/galleryShow.php l. 121-126.
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/view/documentExplorerPreview.php');

/**
 * Can the browser display this file ?
 *
 * The application already answers that in two places, and neither is a list of
 * its own : images in isThumbable() (tool/file.php l. 291), and the extensions
 * that make the mime icon clickable in htmlGetMimeType() (tool/html.php l. 2315),
 * which opens that same tool/download.php. Anything else - doc, xlsx, zip - the
 * browser cannot render, and the application already greys it out.
 *
 * @return bool
 */
function documentExplorerIsPreviewable($fileName) {
  if (! $fileName) return false;
  if (isThumbable($fileName)) return true;
  $ext = pq_strtolower(pathinfo(pq_str_replace('.projeqtor.txt', '', $fileName), PATHINFO_EXTENSION));
  return in_array($ext, array('htm', 'html', 'pdf', 'txt', 'log'));
}

// Position of the list : the collapse bar turns when the list sits on top.
$positionListDiv = Parameter::getUserParameter('paramScreen_DocumentExplorer');

$objectClass = (RequestHandler::isCodeSet('objectClass')) ? RequestHandler::getClass('objectClass') : '';
$objectId    = (RequestHandler::isCodeSet('objectId'))    ? RequestHandler::getId('objectId')       : '';

$previewUrl   = null;
$previewName  = '';
$previewImage = false;

if ($objectClass == 'Document' and $objectId) {
  $document = new Document($objectId);
  if ($document->id and $document->idDocumentVersion) {
    $version = new DocumentVersion($document->idDocumentVersion);
    if ($version->id and documentExplorerIsPreviewable($version->fileName)) {
      // Same call as tool/download.php l. 104 : the stored file carries the id of
      // the version, and the name is sanitized. Reading the path any other way
      // would be a second truth to keep in step.
      $file = $version->getUploadFileName();
      if ($file and file_exists($file)) {
        $previewName  = $version->fileName;
        // An image goes in an <img> and not in the frame : left to itself the
        // browser shows it at its natural size and puts the pane under scrollbars.
        $previewImage = isThumbable($version->fileName);
        $previewUrl   = '../tool/download.php?class=Document&id=' . intval($document->id)
                      . '&showHtml=true' . Security::addTokenIndexToUrl();
      }
    }
  }
}
?>
<div class="documentExplorerPreviewPane">
  <div class="documentExplorerPreviewBar">
    <div class="hideStreamNewGuiTopBar" style="float:left;width:32px;display:block;" onclick="hideDetailScreen();">
      <div class="iconHideMenuRight iconSize32" style="<?php if ($positionListDiv=='top') echo 'transform: rotate(90deg);';?>"></div>
    </div>
    <div class="hideStreamNewGuiTopBar" style="float:left;width:32px;display:block;"
         onclick="documentExplorerShowDetail();" title="<?php echo pq_ucfirst(i18n('colShowDetail'));?>">
      <div class="iconDocument iconSize32"></div>
    </div>
  </div>
<div class="documentExplorerPreview<?php echo ($previewImage) ? ' documentExplorerPreviewCentered' : '';?>">
<?php if ($previewUrl and $previewImage) { ?>
  <img class="documentExplorerPreviewImage" alt="<?php echo htmlEncode($previewName);?>"
       title="<?php echo htmlEncode($previewName);?>" src="<?php echo $previewUrl;?>" />
<?php } else if ($previewUrl) { ?>
  <iframe class="documentExplorerPreviewFrame" title="<?php echo htmlEncode($previewName);?>"
          src="<?php echo $previewUrl;?>"></iframe>
<?php } else { ?>
  <div class="documentExplorerPreviewEmpty"><?php echo i18n('documentExplorerNoPreview');?></div>
<?php } ?>
</div>
</div>
